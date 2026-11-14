#!/usr/bin/env python3
"""Download the reviewed native payload; validate it before staging any files."""
import argparse
import hashlib
import json
import pathlib
import platform
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile

PREFIX = 'usr/lib/bazzite-updater-kde'
MAX_BYTES = 64 * 1024 * 1024
MAX_UNPACKED = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_lock(path):
    lock = json.loads(pathlib.Path(path).read_text())
    require(lock['schema_version'] == 1, 'unsupported lock schema')
    require(re.fullmatch(r'[0-9a-f]{64}', lock['sha256']), 'invalid SHA256 pin')
    require(re.fullmatch(r'[0-9a-f]{40}', lock['source_commit']), 'invalid source pin')
    require(re.fullmatch(r'[0-9a-f]{40}', lock['controllable_commit']), 'invalid Controllable pin')
    require(re.fullmatch(r'[0-9a-f]{40}', lock['packaging_commit']), 'invalid packaging pin')
    require(re.fullmatch(r'\d+\.\d+\.\d+-kde\.\d+', lock['fork_version']), 'invalid fork version')
    require(type(lock['package_revision']) is int and lock['package_revision'] > 0, 'invalid package revision')
    require(lock['architecture'] == 'x86_64' and lock['os_id'] == 'fedora' and isinstance(lock['os_version'], str) and re.fullmatch(r'[1-9][0-9]*', lock['os_version']), 'unsupported package target')
    tag = f"v{lock['fork_version']}-image.{lock['package_revision']}"
    asset = f"bazzite-updater-kde-{lock['fork_version']}-image-{lock['package_revision']}-fedora{lock['os_version']}-x86_64.tar.xz"
    require(lock['release_tag'] == tag and lock['asset'] == asset, 'release/asset identity mismatch')
    lock['url'] = f'https://github.com/jheinem1/bazzite-updater-kde/releases/download/{tag}/{asset}'
    return lock


def validate_archive(archive, lock):
    require(archive.stat().st_size <= MAX_BYTES, 'archive exceeds size limit')
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(digest == lock['sha256'], 'package SHA256 mismatch')
    members = []
    with tarfile.open(archive, 'r:xz') as tar:
        seen = set()
        total = 0
        for member in tar:
            require(len(members) < 10000, 'too many archive entries')
            name = member.name.removeprefix('./').rstrip('/')
            require(name and not name.startswith('/') and '..' not in name.split('/'), 'unsafe archive path')
            require(posixpath.normpath(name) == name, 'noncanonical archive path')
            require(name == PREFIX or name.startswith(PREFIX + '/') or (member.isdir() and name in ('usr', 'usr/lib')), 'path outside private payload')
            require(name not in seen, 'duplicate archive path')
            require(not name.endswith('/runtime-verified'), 'package must not claim final-image verification')
            require(member.isdir() or member.isfile() or member.issym(), 'unsupported archive member')
            require(not member.mode & 0o7000, 'unsafe file mode')
            if member.issym():
                require(not member.linkname.startswith('/'), 'absolute symlink')
                require('..' not in member.linkname.split('/'), 'parent traversal in symlink target')
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                require(target.startswith(PREFIX + '/'), 'symlink escapes private payload')
            total += member.size
            require(total <= MAX_UNPACKED, 'unpacked payload exceeds size limit')
            member.name = name
            seen.add(name)
            members.append(member)
        symlinks = {m.name for m in members if m.issym()}
        for member in members:
            require(not any(parent.as_posix() in symlinks for parent in pathlib.PurePosixPath(member.name).parents), 'entry below symlink')
        entries = {m.name: m for m in members}
        def read(name):
            member = entries.get(PREFIX + '/' + name)
            require(member is not None and member.isfile() and member.size < 1024 * 1024, 'missing/invalid metadata: ' + name)
            return tar.extractfile(member).read().decode('utf-8')
        require(read('source-commit').strip() == lock['source_commit'], 'source commit mismatch')
        require(read('fork-version').strip() == lock['fork_version'], 'fork version mismatch')
        info = json.loads(read('BUILD-INFO.json'))
        for key in ('source_commit', 'fork_version', 'architecture', 'os_id', 'os_version', 'package_revision', 'controllable_commit', 'packaging_commit'):
            require(info.get(key) == lock[key], 'build metadata mismatch: ' + key)
        require(info.get('ui_probe') is False, 'production UI probe must be OFF')
        require(re.fullmatch(r'ghcr\.io/ublue-os/bazzite@sha256:[0-9a-f]{64}', info.get('builder_image', '')), 'builder digest missing')
        executable = entries.get(PREFIX + '/bin/bazzite-updater')
        require(executable is not None and executable.isfile() and executable.mode & 0o111, 'missing native executable')
        require(hashlib.file_digest(tar.extractfile(executable), 'sha256').hexdigest() == info.get('binary_sha256'), 'native executable digest mismatch')
    return members


def stage(archive, lock, destination):
    require(platform.machine() == lock['architecture'], 'build architecture mismatch')
    require(not destination.exists(), 'destination must not already exist')
    members = validate_archive(archive, lock)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='updater-stage-', dir=destination.parent) as tmp:
        root = pathlib.Path(tmp) / 'payload'
        root.mkdir()
        with tarfile.open(archive, 'r:xz') as tar:
            for member in members:
                path = root / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                if member.isdir():
                    path.mkdir(exist_ok=True)
                elif member.isfile():
                    with tar.extractfile(member) as source, path.open('xb') as target:
                        shutil.copyfileobj(source, target)
                    path.chmod(member.mode & 0o777)
            for member in members:
                if member.issym():
                    (root / member.name).symlink_to(member.linkname)
        root.rename(destination)


def verify_build_target(lock):
    require(platform.machine() == lock['architecture'], 'build architecture mismatch')
    require(platform.freedesktop_os_release().get('VERSION_ID') == lock['os_version'], 'build Fedora release mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=pathlib.Path, required=True)
    parser.add_argument('--destination', type=pathlib.Path, required=True)
    parser.add_argument('--archive', type=pathlib.Path, help='Verify an already downloaded archive against the same lock')
    args = parser.parse_args()
    lock = read_lock(args.lock)
    verify_build_target(lock)
    with tempfile.TemporaryDirectory(prefix='updater-download-') as tmp:
        archive = args.archive or pathlib.Path(tmp) / 'package.tar.xz'
        if not args.archive:
            subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                            '--retry', '2', '--connect-timeout', '20', '--max-time', '180',
                            '--max-filesize', str(MAX_BYTES), '--output', str(archive), lock['url']],
                           check=True, timeout=600)
        stage(archive, lock, args.destination)
    print('updater package: checksum, provenance and private payload verified')


if __name__ == '__main__':
    main()

"""Exercise package acquisition with inert, locally generated release archives."""
import hashlib
import importlib.util
import io
import json
import pathlib
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('acquire', ROOT / 'system/bazzite-updater-kde/acquire.py')
acquire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquire)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.lock = dict(schema_version=1, sha256='a' * 64, source_commit='b' * 40,
                         controllable_commit='c' * 40, packaging_commit='f' * 40, fork_version='1.2.1-kde.3',
                         package_revision=2, architecture='x86_64', os_id='fedora', os_version='45',
                         release_tag='v1.2.1-kde.3-image.2',
                         asset='bazzite-updater-kde-1.2.1-kde.3-image-2-fedora45-x86_64.tar.xz')
        self.info = dict(self.lock, ui_probe=False, builder_image='ghcr.io/ublue-os/bazzite@sha256:' + 'd' * 64,
                         binary_sha256=hashlib.sha256(b'inert executable').hexdigest())

    def make_archive(self, extra=(), metadata=None):
        archive = self.root / 'package.tar.xz'
        files = {'source-commit':self.lock['source_commit']+'\n', 'fork-version':self.lock['fork_version']+'\n',
                 'BUILD-INFO.json':json.dumps(metadata or self.info), 'bin/bazzite-updater':'inert executable'}
        with tarfile.open(archive, 'w:xz') as tar:
            for name, data in files.items():
                item = tarfile.TarInfo(acquire.PREFIX + '/' + name)
                item.mode = 0o755 if name.startswith('bin/') else 0o644
                item.size = len(data.encode())
                tar.addfile(item, io.BytesIO(data.encode()))
            for item in extra:
                tar.addfile(item, io.BytesIO(b'X' * item.size) if item.isfile() else None)
        self.lock['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        return archive

    def validate(self, extra=(), metadata=None):
        return acquire.validate_archive(self.make_archive(extra, metadata), self.lock)

    def test_success_stages_private_files_and_relative_links(self):
        link=tarfile.TarInfo(acquire.PREFIX+'/bin/alias'); link.type=tarfile.SYMTYPE; link.linkname='bazzite-updater'
        archive=self.make_archive([link])
        with mock.patch.object(acquire.platform, 'machine', return_value='x86_64'):
            acquire.stage(archive, self.lock, self.root/'out')
        self.assertEqual((self.root/'out'/acquire.PREFIX/'bin/alias').read_text(), 'inert executable')
        self.assertFalse((self.root/'out'/acquire.PREFIX/'runtime-verified').exists())

    def test_checksum_before_archive_parse(self):
        archive=self.root/'broken'; archive.write_bytes(b'not a tar')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            acquire.validate_archive(archive, self.lock)

    def test_metadata_mismatch(self):
        for key,value in [('source_commit','e'*40),('fork_version','1.2.1-kde.2'),('architecture','aarch64'),
                          ('os_version','44'),('controllable_commit','e'*40),('packaging_commit','e'*40),('package_revision',1),
                          ('ui_probe',True),('builder_image','ghcr.io/ublue-os/bazzite:stable'),('binary_sha256','e'*64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(metadata=dict(self.info, **{key:value}))

    def test_unsafe_paths(self):
        for name in ['/tmp/outside','../outside',acquire.PREFIX+'/../../escape','etc/overwrite',acquire.PREFIX+'/runtime-verified']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate([tarfile.TarInfo(name)])

    def test_unsafe_links(self):
        for target in ['/etc/passwd','../../../../escape','bin/../bin/bazzite-updater']:
            link=tarfile.TarInfo(acquire.PREFIX+'/link'); link.type=tarfile.SYMTYPE; link.linkname=target
            with self.subTest(target=target), self.assertRaises(ValueError): self.validate([link])

    def test_entry_under_link(self):
        link=tarfile.TarInfo(acquire.PREFIX+'/alias'); link.type=tarfile.SYMTYPE; link.linkname='bin'
        with self.assertRaisesRegex(ValueError, 'below symlink'):
            self.validate([link,tarfile.TarInfo(acquire.PREFIX+'/alias/file')])

    def test_hardlink_and_device_rejected(self):
        for kind in [tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE]:
            member=tarfile.TarInfo(acquire.PREFIX+'/bad'); member.type=kind
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.validate([member])

    def test_setuid_rejected(self):
        item=tarfile.TarInfo(acquire.PREFIX+'/bad'); item.mode=0o4755
        with self.assertRaisesRegex(ValueError,'mode'): self.validate([item])

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.validate([tarfile.TarInfo(acquire.PREFIX+'/source-commit')])

    def test_architecture_and_existing_destination_fail_closed(self):
        archive=self.make_archive()
        with mock.patch.object(acquire.platform,'machine',return_value='aarch64'), self.assertRaisesRegex(ValueError,'architecture'):
            acquire.stage(archive,self.lock,self.root/'out')
        with mock.patch.object(acquire.platform,'machine',return_value='x86_64'), self.assertRaisesRegex(ValueError,'already exist'):
            acquire.stage(archive,self.lock,self.root)

    def test_read_lock_restricts_release_identity(self):
        path=self.root/'lock.json'; path.write_text(json.dumps(self.lock))
        self.assertTrue(acquire.read_lock(path)['url'].startswith('https://github.com/jheinem1/bazzite-updater-kde/releases/download/'))
        self.lock['asset']='../../../evil'; path.write_text(json.dumps(self.lock))
        with self.assertRaises(ValueError): acquire.read_lock(path)

    def test_explicit_fedora_target_controls_asset_name(self):
        path=self.root/'lock.json'
        for version in ('44', '45'):
            lock=dict(self.lock, os_version=version,
                      asset=f'bazzite-updater-kde-1.2.1-kde.3-image-2-fedora{version}-x86_64.tar.xz')
            path.write_text(json.dumps(lock))
            self.assertEqual(acquire.read_lock(path)['os_version'], version)
        for version in ('latest', '45/../escape', 45, ''):
            path.write_text(json.dumps(dict(self.lock, os_version=version)))
            with self.subTest(version=version), self.assertRaises(ValueError): acquire.read_lock(path)

    def test_builder_os_must_match_explicit_target(self):
        with mock.patch.object(acquire.platform,'machine',return_value='x86_64'):
            with mock.patch.object(acquire.platform,'freedesktop_os_release',return_value={'ID':'bazzite','VERSION_ID':'45'}):
                acquire.verify_build_target(self.lock)
            with mock.patch.object(acquire.platform,'freedesktop_os_release',return_value={'ID':'bazzite','VERSION_ID':'44'}):
                with self.assertRaisesRegex(ValueError,'release mismatch'): acquire.verify_build_target(self.lock)

    def test_repository_lock_pins_published_package(self):
        lock=acquire.read_lock(ROOT/'system/bazzite-updater-kde/package.json')
        self.assertEqual(lock['release_tag'], 'v1.2.1-kde.3-image.4')
        self.assertEqual(lock['os_version'], '45')
        self.assertEqual(lock['source_commit'], '9ea7804bf9f94c618baa48fbe75ea5b1168e46bf')
        self.assertEqual(lock['sha256'], 'b3bcd876f2dc2bf583a776a9729b4542d38e7b8ae05cdb72ee369506dd4047fc')

    def test_container_preserves_runtime_verification(self):
        container=(ROOT/'Containerfile').read_text()
        self.assertNotIn('updater-builder',container)
        self.assertIn('acquire.py --lock /tmp/kde-updater/package.json --destination /out',container)
        self.assertIn('timeout --kill-after=5s 45s bash /tmp/kde-updater-verify',container)
        self.assertIn('/usr/libexec/bazzite-updater-upstream',container)


if __name__=='__main__': unittest.main()

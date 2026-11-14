#!/usr/bin/env python3
"""Fail closed on missing publisher key or an existing remote with other trust."""
import configparser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def primary_keys(path):
    # Isolated, read-only key inspection: never import into the user's keyring.
    with tempfile.TemporaryDirectory() as home:
        result = subprocess.check_output(['gpg', '--batch', '--homedir', home,
            '--with-colons', '--import-options', 'show-only', '--dry-run', '--import', str(path)], text=True)
    keys = []
    primary = False
    for line in result.splitlines():
        fields = line.split(':')
        if fields[0] == 'pub':
            if fields[1] in ('r', 'e', 'd'):
                raise ValueError('Publisher key is revoked, expired or disabled')
            primary = True
        elif fields[0] == 'sub':
            primary = False
        elif fields[0] == 'fpr' and primary:
            keys.append(fields[9])
            primary = False
    return keys


def validate(assets, repo=None):
    assets = Path(assets)
    r = json.loads((assets / 'repository.json').read_text())
    for key, expected in dict(app_id='io.github.jheinem1.PiperKirigami', branch='development',
            architecture='x86_64', remote='piper-kirigami',
            url='https://jheinem1.github.io/piper-kirigami/repo/', public_key='piper-repository.gpg').items():
        if r.get(key) != expected:
            raise ValueError('Unexpected repository ' + key)
    fingerprint = r.get('gpg_fingerprint')
    if not isinstance(fingerprint, str) or not re.fullmatch(r'[0-9A-F]{40}', fingerprint):
        raise ValueError('Piper repository signing key has not been provisioned')
    if primary_keys(assets / r['public_key']) != [fingerprint]:
        raise ValueError('Publisher public key fingerprint mismatch')
    if repo is not None:
        repo = Path(repo)
        config = configparser.ConfigParser(interpolation=None)
        config.read(repo / 'config')
        section = 'remote "' + r['remote'] + '"'
        if section not in config:
            return r, False
        remote = config[section]
        if remote.get('url') != r['url']:
            raise ValueError('Existing Piper remote URL differs; refusing to change it')
        if not remote.getboolean('gpg-verify', fallback=False) or not remote.getboolean('gpg-verify-summary', fallback=True):
            raise ValueError('Existing Piper remote has signature verification disabled')
        if primary_keys(repo / (r['remote'] + '.trustedkeys.gpg')) != [fingerprint]:
            raise ValueError('Existing Piper remote trusts a different signing key')
        return r, True
    return r, False


if __name__ == '__main__':
    try:
        r, exists = validate(*sys.argv[1:])
        for key in ('remote', 'url', 'app_id', 'architecture', 'branch', 'public_key'):
            print(r[key])
        print('present' if exists else 'absent')
    except (ValueError, OSError, subprocess.CalledProcessError, configparser.Error) as error:
        sys.exit('Piper repository verification failed: ' + str(error))

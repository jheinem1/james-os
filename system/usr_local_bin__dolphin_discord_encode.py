#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import which

ENCODER = Path('/usr/local/bin/discord_encoder.py')


def run_kdialog_input() -> str | None:
    try:
        proc = subprocess.run(
            [
                'kdialog',
                '--title', 'Discord H.264 Encode',
                '--inputbox', 'Target file size in MB (decimal):', '50',
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        subprocess.run(['notify-send', 'Discord Encode', 'kdialog is not installed'], check=False)
        return None

    if proc.returncode != 0:
        return None

    return proc.stdout.strip()


def validate_size(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    if v <= 1:
        return None
    return v


class ProgressDialog:
    def __init__(self) -> None:
        self.qdbus_bin = which('qdbus6') or which('qdbus-qt6') or which('qdbus')
        self.service: str | None = None
        self.path: str | None = None

    def open(self, text: str) -> bool:
        if not self.qdbus_bin:
            return False
        proc = subprocess.run(
            ['kdialog', '--title', 'Discord H.264 Encode', '--progressbar', text, '100'],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return False
        ref = proc.stdout.strip()
        parts = ref.split(maxsplit=1)
        if len(parts) != 2:
            return False
        self.service, self.path = parts[0], parts[1]
        return True

    def _call(self, method: str, *args: str) -> None:
        if not self.qdbus_bin or not self.service or not self.path:
            return
        subprocess.run(
            [self.qdbus_bin, self.service, self.path, method, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def update(self, pct: int, text: str | None = None) -> None:
        pct = max(0, min(100, int(pct)))
        self._call('Set', '', 'value', str(pct))
        if text:
            self._call('setLabelText', text)

    def close(self) -> None:
        self._call('close')


def parse_progress_line(line: str) -> tuple[int, str] | None:
    if not line.startswith('__PROGRESS__:'):
        return None
    parts = line.rstrip('\n').split(':', 2)
    if len(parts) != 3:
        return None
    try:
        pct = int(parts[1])
    except ValueError:
        return None
    return pct, parts[2]


def main(argv: list[str]) -> int:
    files = [a for a in argv if a.strip()]
    if not files:
        subprocess.run(['kdialog', '--error', 'No files selected.'], check=False)
        return 1

    if not ENCODER.exists():
        subprocess.run(['kdialog', '--error', f'Encoder script not found: {ENCODER}'], check=False)
        return 1

    size_text = run_kdialog_input()
    if size_text is None:
        return 0

    size_value = validate_size(size_text)
    if size_value is None:
        subprocess.run(['kdialog', '--error', f'Invalid size: {size_text}'], check=False)
        return 1

    log_file = Path('/tmp') / f'discord_h264_encode_{Path(files[0]).stem}.log'
    cmd = ['python3', str(ENCODER), '--progress-lines', '--size-mb', str(size_value), *files]

    progress = ProgressDialog()
    has_progress = progress.open('Preparing...')
    if has_progress:
        progress.update(0, 'Starting encode...')

    rc = 1
    with log_file.open('w', encoding='utf-8') as f:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if proc.stdout is not None:
            for line in proc.stdout:
                f.write(line)
                parsed = parse_progress_line(line)
                if parsed and has_progress:
                    pct, label = parsed
                    progress.update(pct, f'Encoding... {pct}% ({label})')
        rc = proc.wait()

    if has_progress:
        progress.update(100, 'Finishing...')
        progress.close()

    if rc == 0:
        subprocess.run(['kdialog', '--passivepopup', 'Discord H.264 encoding finished.', '5'], check=False)
        return 0

    subprocess.run(['kdialog', '--error', f'Encoding failed. Log: {log_file}'], check=False)
    return rc


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

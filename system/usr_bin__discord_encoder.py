#!/usr/bin/env python3
"""Encode videos for Discord using CPU H.264 with a target size limit."""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class EncodeSettings:
    size_mb: float
    audio_kbps: int
    preset: str
    retry_on_overshoot: bool


def have_bin(name: str) -> bool:
    return shutil.which(name) is not None


def ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    duration = float(out)
    if duration <= 0:
        raise ValueError("duration must be > 0")
    return duration


def calc_video_kbps(size_mb: float, duration_s: float, audio_kbps: int, safety: float = 0.985) -> int:
    total_bits = size_mb * 1_000_000 * 8
    total_bps = total_bits / duration_s
    video_bps = (total_bps - (audio_kbps * 1000)) * safety
    return max(100, int(video_bps // 1000))


def unique_output_path(output_dir: Path, source: Path) -> Path:
    base = source.stem
    out = output_dir / f"{base}_discord_h264.mp4"
    if not out.exists():
        return out
    i = 1
    while True:
        candidate = output_dir / f"{base}_discord_h264_{i}.mp4"
        if not candidate.exists():
            return candidate
        i += 1


def run_cmd(cmd: list[str]) -> int:
    print("$", " ".join(subprocess.list2cmdline([part]) for part in cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def run_ffmpeg_with_progress(
    cmd: list[str],
    duration_s: float,
    progress_cb: Callable[[float], None] | None = None,
) -> int:
    if progress_cb is None:
        return run_cmd(cmd)

    progress_cmd = [cmd[0], "-nostats", "-progress", "pipe:1", *cmd[1:]]
    print("$", " ".join(subprocess.list2cmdline([part]) for part in progress_cmd))
    proc = subprocess.Popen(
        progress_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        return proc.wait()

    duration_ms = max(1, int(duration_s * 1000))
    last_progress = -1.0

    for raw_line in proc.stdout:
        line = raw_line.rstrip("\n")
        if line.startswith("out_time_ms="):
            try:
                out_time_ms = int(line.split("=", 1)[1])
                pct = max(0.0, min(1.0, out_time_ms / duration_ms))
                if pct >= last_progress + 0.002:
                    progress_cb(pct)
                    last_progress = pct
            except ValueError:
                pass
        elif line == "progress=end":
            progress_cb(1.0)
        else:
            print(line)

    return proc.wait()


def build_pass_cmds(
    source: Path,
    output: Path,
    passlog_prefix: Path,
    video_kbps: int,
    audio_kbps: int,
    preset: str,
) -> tuple[list[str], list[str]]:
    common_video = [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-b:v",
        f"{video_kbps}k",
        "-profile:v",
        "high",
        "-level:v",
        "4.1",
        "-pix_fmt",
        "yuv420p",
    ]

    pass1 = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        *common_video,
        "-pass",
        "1",
        "-passlogfile",
        str(passlog_prefix),
        "-an",
        "-f",
        "null",
        "/dev/null",
    ]

    pass2 = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        *common_video,
        "-pass",
        "2",
        "-passlogfile",
        str(passlog_prefix),
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_kbps}k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    return pass1, pass2


def cleanup_two_pass_files(passlog_prefix: Path) -> None:
    for suffix in ("-0.log", "-0.log.mbtree"):
        p = Path(str(passlog_prefix) + suffix)
        if p.exists():
            p.unlink(missing_ok=True)


def encode_one(
    source: Path,
    output_dir_override: Path | None,
    settings: EncodeSettings,
    progress_cb: Callable[[float], None] | None = None,
) -> int:
    if not source.exists() or not source.is_file():
        print(f"ERROR: not a file: {source}", file=sys.stderr)
        return 1

    output_dir = output_dir_override if output_dir_override else source.parent / "encoded"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = unique_output_path(output_dir, source)

    try:
        duration_s = ffprobe_duration(source)
    except Exception as exc:
        print(f"ERROR: ffprobe failed for {source}: {exc}", file=sys.stderr)
        return 1

    target_bytes = int(settings.size_mb * 1_000_000)
    initial_video_kbps = calc_video_kbps(settings.size_mb, duration_s, settings.audio_kbps)
    attempts = 2 if settings.retry_on_overshoot else 1
    current_video_kbps = initial_video_kbps

    print(f"Encoding: {source}")
    print(f"Target size: {settings.size_mb:.2f} MB | Duration: {duration_s:.2f}s")

    for attempt in range(1, attempts + 1):
        total_passes = attempts * 2
        pass_base_1 = ((attempt - 1) * 2) / total_passes
        pass_base_2 = ((attempt - 1) * 2 + 1) / total_passes
        pass_span = 1.0 / total_passes
        with tempfile.TemporaryDirectory(prefix="discord_h264_passlog_") as tmpdir:
            passlog_prefix = Path(tmpdir) / "x264pass"
            pass1, pass2 = build_pass_cmds(
                source=source,
                output=output,
                passlog_prefix=passlog_prefix,
                video_kbps=current_video_kbps,
                audio_kbps=settings.audio_kbps,
                preset=settings.preset,
            )

            print(
                f"Attempt {attempt}/{attempts}: v_bitrate={current_video_kbps}k "
                f"a_bitrate={settings.audio_kbps}k preset={settings.preset}"
            )

            pass1_cb = None
            if progress_cb is not None:
                pass1_cb = lambda p: progress_cb(pass_base_1 + (p * pass_span))
            rc = run_ffmpeg_with_progress(pass1, duration_s, pass1_cb)
            if rc != 0:
                print("ERROR: pass 1 failed", file=sys.stderr)
                cleanup_two_pass_files(passlog_prefix)
                return rc

            pass2_cb = None
            if progress_cb is not None:
                pass2_cb = lambda p: progress_cb(pass_base_2 + (p * pass_span))
            rc = run_ffmpeg_with_progress(pass2, duration_s, pass2_cb)
            cleanup_two_pass_files(passlog_prefix)
            if rc != 0:
                print("ERROR: pass 2 failed", file=sys.stderr)
                return rc

        actual_bytes = output.stat().st_size if output.exists() else 0
        actual_mb = actual_bytes / 1_000_000 if actual_bytes else 0
        print(f"Output: {output} ({actual_mb:.2f} MB)")

        if actual_bytes <= target_bytes:
            return 0

        if attempt == attempts:
            print(
                f"ERROR: output exceeds target ({actual_mb:.2f} MB > {settings.size_mb:.2f} MB)",
                file=sys.stderr,
            )
            return 2

        overshoot_ratio = actual_bytes / target_bytes
        next_factor = max(0.4, min(0.95, (1.0 / overshoot_ratio) * 0.98))
        current_video_kbps = max(100, int(math.floor(current_video_kbps * next_factor)))
        print(
            f"Overshoot detected ({overshoot_ratio:.3f}x). Retrying with {current_video_kbps}k video bitrate."
        )

    if progress_cb is not None:
        progress_cb(1.0)
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CPU H.264 two-pass encoder for Discord with size targeting."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Input video file(s).",
    )
    parser.add_argument(
        "--size-mb",
        type=float,
        required=True,
        help="Target output file size in decimal MB (1 MB = 1,000,000 bytes).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional output directory. Defaults to an 'encoded' folder next to each input file.",
    )
    parser.add_argument(
        "--audio-kbps",
        type=int,
        default=128,
        help="AAC audio bitrate (default: 128).",
    )
    parser.add_argument(
        "--preset",
        default="veryslow",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
            "placebo",
        ],
        help="x264 preset (default: veryslow).",
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable single retry when output exceeds target size.",
    )
    parser.add_argument(
        "--progress-lines",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.size_mb <= 1:
        print("ERROR: --size-mb must be greater than 1", file=sys.stderr)
        return 2

    if args.audio_kbps < 32 or args.audio_kbps > 320:
        print("ERROR: --audio-kbps must be between 32 and 320", file=sys.stderr)
        return 2

    missing = [b for b in ("ffmpeg", "ffprobe") if not have_bin(b)]
    if missing:
        print(f"ERROR: missing dependencies: {', '.join(missing)}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve() if args.output_dir else None
    settings = EncodeSettings(
        size_mb=args.size_mb,
        audio_kbps=args.audio_kbps,
        preset=args.preset,
        retry_on_overshoot=(not args.no_retry),
    )

    failures = 0
    total_files = len(args.inputs)
    for idx, src in enumerate(args.inputs):
        source_name = src.name

        def report_file_progress(file_progress: float) -> None:
            clamped = max(0.0, min(1.0, file_progress))
            overall = ((idx + clamped) / total_files) * 100.0
            if args.progress_lines:
                print(f"__PROGRESS__:{int(overall)}:{source_name}", flush=True)

        rc = encode_one(src.resolve(), output_dir, settings, report_file_progress)
        if rc != 0:
            failures += 1
    if args.progress_lines and failures == 0:
        print("__PROGRESS__:100:Done", flush=True)

    if failures:
        print(f"Completed with failures: {failures}/{len(args.inputs)}", file=sys.stderr)
        return 1

    print(f"Completed successfully: {len(args.inputs)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

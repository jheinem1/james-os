#!/usr/bin/env python3

import os
import socket
import subprocess
import time


SOCKET_PATH = os.environ.get(
    "VENCORD_KDE_IDLE_SOCKET",
    os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "vencord-kde-idle-sync.sock"),
)
IDLE_THRESHOLD_SECONDS = int(os.environ.get("VENCORD_KDE_IDLE_THRESHOLD", "300"))
POLL_SECONDS = float(os.environ.get("VENCORD_KDE_IDLE_POLL_SECONDS", "5"))


def dbus_call(method: str) -> str:
    result = subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.ScreenSaver",
            "--object-path",
            "/org/freedesktop/ScreenSaver",
            "--method",
            f"org.freedesktop.ScreenSaver.{method}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_lock_state() -> bool:
    return dbus_call("GetActive").lower().endswith("true,)")


def get_idle_seconds() -> int:
    output = dbus_call("GetSessionIdleTime")
    return int(output.removeprefix("(uint32 ").removesuffix(",)"))


def notify_vencord(state: str) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(SOCKET_PATH)
        client.sendall(f"{state}\n".encode())


def main() -> None:
    last_state = None

    while True:
        try:
            state = "inactive" if get_lock_state() or get_idle_seconds() >= IDLE_THRESHOLD_SECONDS else "active"
            if state != last_state:
                notify_vencord(state)
                last_state = state
        except Exception:
            pass

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

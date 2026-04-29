#!/usr/bin/env python3
"""with_server.py — start a dev server, wait for ports to listen, manage teardown.

Used by webapp-test-orchestrator skill to bring up a project's dev server
before Playwright runs. Black-box: invoke with --help, do not read source.

Examples:
    # Front-end only on port 3000
    with_server.py --frontend 3000 --command "npm run dev"

    # Front + back, separate commands
    with_server.py --frontend 3000 --backend 8000 \\
        --command "npm run dev" --backend-command "uvicorn app:app --port 8000"

    # Use playwright.config.ts webServer instead — just wait for ports
    with_server.py --frontend 3000 --backend 8000 --wait-only

The script blocks. It prints a single line "READY" to stdout when all
target ports are listening, then keeps the child processes alive until
SIGTERM/SIGINT, at which point it tears them down gracefully.
"""
from __future__ import annotations

import argparse
import os
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time

# Windows stdout often defaults to cp1252; force UTF-8 so Cyrillic paths and
# em-dashes don't crash with UnicodeEncodeError. No-op on Linux/macOS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


def _is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _wait_for_port(port: int, timeout_s: float, label: str) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        if _is_port_listening(port):
            print(f"[with_server] {label} :{port} listening", file=sys.stderr)
            return True
        time.sleep(0.5)
    return False


def _spawn(command: str, cwd: str | None, extra_env: dict[str, str], label: str) -> subprocess.Popen:
    print(f"[with_server] starting {label}: {command}", file=sys.stderr)
    env = os.environ.copy()
    env.update(extra_env)
    if os.name == "nt":
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            stdout=sys.stderr,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined, unused-ignore]
        )
    else:
        proc = subprocess.Popen(
            shlex.split(command),
            cwd=cwd,
            env=env,
            stdout=sys.stderr,
            stderr=sys.stderr,
            preexec_fn=os.setsid,  # type: ignore[attr-defined, unused-ignore]  # POSIX only
        )
    return proc


def _terminate(proc: subprocess.Popen, label: str, grace_s: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    print(f"[with_server] terminating {label} (pid {proc.pid})", file=sys.stderr)
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined, unused-ignore]
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)  # type: ignore[attr-defined, unused-ignore]
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        print(f"[with_server] killing {label} (pid {proc.pid})", file=sys.stderr)
        try:
            if os.name == "nt":
                proc.kill()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # type: ignore[attr-defined, unused-ignore]
        except (ProcessLookupError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Spawn dev server(s), wait for ports, hold open until SIGTERM/SIGINT.",
    )
    parser.add_argument("--frontend", type=int, help="Frontend port to wait for")
    parser.add_argument("--backend", type=int, help="Backend port to wait for")
    parser.add_argument("--command", help="Command to run for the frontend")
    parser.add_argument("--backend-command", help="Optional separate backend command")
    parser.add_argument("--cwd", default=".", help="Working directory for spawned commands")
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Seconds to wait for each port to listen (default 90)",
    )
    parser.add_argument(
        "--wait-only",
        action="store_true",
        help="Don't spawn anything; just wait for ports to come up. Useful when "
        "playwright.config.ts has its own webServer block.",
    )
    parser.add_argument(
        "--print-ready-line",
        default="READY",
        help="Stdout sentinel printed once all ports are listening (default 'READY')",
    )
    args = parser.parse_args(argv)

    if not args.frontend and not args.backend:
        parser.error("at least one of --frontend or --backend is required")
    if args.wait_only and (args.command or args.backend_command):
        parser.error("--wait-only is incompatible with --command/--backend-command")
    if not args.wait_only and not args.command:
        parser.error("--command is required unless --wait-only")

    children: list[tuple[subprocess.Popen, str]] = []
    if not args.wait_only:
        front_env = {}
        if args.frontend:
            front_env["PORT"] = str(args.frontend)
        children.append((_spawn(args.command, args.cwd, front_env, "frontend"), "frontend"))
        if args.backend_command:
            back_env = {}
            if args.backend:
                back_env["PORT"] = str(args.backend)
            children.append(
                (_spawn(args.backend_command, args.cwd, back_env, "backend"), "backend")
            )

    targets: list[tuple[int, str]] = []
    if args.frontend:
        targets.append((args.frontend, "frontend"))
    if args.backend:
        targets.append((args.backend, "backend"))

    for port, label in targets:
        if not _wait_for_port(port, args.timeout, label):
            for proc, lbl in children:
                _terminate(proc, lbl)
            print(f"[with_server] timeout: {label} :{port} never listened", file=sys.stderr)
            return 1

    print(args.print_ready_line, flush=True)

    stop_event = threading.Event()

    def _handle_sig(signum, _frame):
        print(f"[with_server] received signal {signum}, tearing down", file=sys.stderr)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sig)

    try:
        while not stop_event.is_set():
            for proc, label in children:
                rc = proc.poll()
                if rc is not None:
                    print(
                        f"[with_server] {label} exited unexpectedly with code {rc}",
                        file=sys.stderr,
                    )
                    stop_event.set()
                    break
            stop_event.wait(timeout=1.0)
    finally:
        for proc, label in children:
            _terminate(proc, label)

    return 0


if __name__ == "__main__":
    sys.exit(main())

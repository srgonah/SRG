#!/usr/bin/env python3
"""
SRG management CLI.

Usage:
    python manage.py start       Build dashboard & start server
    python manage.py stop        Graceful shutdown
    python manage.py restart     Stop + start
    python manage.py dev         Backend (reload) + Vite dev server
    python manage.py build       Build dashboard only
    python manage.py status      Check if server is running
"""

import argparse
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PID_FILE = ROOT_DIR / ".srg.pid"
DASHBOARD_DIR = ROOT_DIR / "dashboard"
STATIC_DIR = ROOT_DIR / "static"

IS_WINDOWS = platform.system() == "Windows"


def _read_pid() -> int | None:
    """Read PID from .srg.pid file, return None if missing or stale."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None
    # Check if process is alive
    if _is_pid_alive(pid):
        return pid
    # Stale PID file
    PID_FILE.unlink(missing_ok=True)
    return None


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        except OSError:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _write_pid(pid: int) -> None:
    PID_FILE.write_text(str(pid))


def _kill_pid(pid: int) -> bool:
    """Send termination signal to a process. Returns True if successful."""
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
            )
            return True
        except OSError:
            return False
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False


def _find_pid_on_port(port: int) -> int | None:
    """Find the PID of the process listening on the given port."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines():
                # Match lines like "  TCP    0.0.0.0:8000  ...  LISTENING  1234"
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    try:
                        return int(parts[-1])
                    except (ValueError, IndexError):
                        continue
        except OSError:
            pass
    else:
        # Try lsof first (macOS and most Linux)
        try:
            result = subprocess.run(
                ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().splitlines()[0])
        except (OSError, ValueError):
            pass
        # Fall back to ss (Linux without lsof)
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
            )
            match = re.search(r"pid=(\d+)", result.stdout)
            if match:
                return int(match.group(1))
        except (OSError, ValueError):
            pass
    return None


def _is_port_free(port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def _wait_for_port_free(port: int, timeout: float = 5.0) -> bool:
    """Poll until port is free or timeout expires. Returns True if port is free."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_port_free(port):
            return True
        time.sleep(0.25)
    return _is_port_free(port)


def _free_port(port: int) -> bool:
    """Find and kill whatever process holds the port. Returns True on success."""
    pid = _find_pid_on_port(port)
    if pid is None:
        # Port occupied but can't identify process
        if IS_WINDOWS:
            print(f"Error: Port {port} is in use but the owning process could not be identified.")
            print("  Try: netstat -ano | findstr :8000   (from an admin shell)")
        else:
            print(f"Error: Port {port} is in use but the owning process could not be identified.")
            print(f"  Try: sudo lsof -ti TCP:{port}")
        return False

    print(f"Port {port} is held by PID {pid}. Attempting to terminate...")

    if IS_WINDOWS:
        killed = False
        # Strategy 1: taskkill
        try:
            r = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                killed = True
        except OSError:
            pass

        # Strategy 2: wmic (older Windows)
        if not killed:
            try:
                r = subprocess.run(
                    ["wmic", "process", "where", f"ProcessId={pid}", "delete"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode == 0:
                    killed = True
            except OSError:
                pass

        # Strategy 3: PowerShell
        if not killed:
            try:
                r = subprocess.run(
                    ["powershell", "-Command", f"Stop-Process -Id {pid} -Force"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode == 0:
                    killed = True
            except OSError:
                pass
    else:
        # Unix: SIGTERM first, then SIGKILL
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    if _wait_for_port_free(port, timeout=5.0):
        print(f"Port {port} is now free.")
        return True

    # Last resort on Unix: SIGKILL
    if not IS_WINDOWS:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        if _wait_for_port_free(port, timeout=3.0):
            print(f"Port {port} is now free (after SIGKILL).")
            return True

    if IS_WINDOWS:
        print(f"Error: Could not free port {port}. Try running as Administrator:")
        print(f"  taskkill /PID {pid} /T /F")
    else:
        print(f"Error: Could not free port {port}. Try:")
        print(f"  sudo kill -9 {pid}")
    return False


def build_dashboard() -> bool:
    """Build the React dashboard into static/."""
    if not DASHBOARD_DIR.exists():
        print("Error: dashboard/ directory not found.")
        return False

    node_modules = DASHBOARD_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing dashboard dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(DASHBOARD_DIR),
            shell=IS_WINDOWS,
        )
        if result.returncode != 0:
            print("Error: npm install failed.")
            return False

    print("Building dashboard...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(DASHBOARD_DIR),
        shell=IS_WINDOWS,
    )
    if result.returncode != 0:
        print("Error: Dashboard build failed.")
        return False

    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        print(f"Dashboard built -> {STATIC_DIR}")
        return True
    else:
        print("Error: Build completed but static/index.html not found.")
        return False


def cmd_build(args: argparse.Namespace) -> None:
    """Build dashboard only."""
    if not build_dashboard():
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    """Build dashboard and start the server."""
    # Check if already running
    existing_pid = _read_pid()
    if existing_pid is not None:
        print(f"Server already running (PID {existing_pid}). Use 'restart' or 'stop' first.")
        sys.exit(1)

    port = args.port
    if not _is_port_free(port):
        print(f"Port {port} is occupied by an unknown process.")
        if not _free_port(port):
            sys.exit(1)

    # Build unless --skip-build
    if not args.skip_build:
        if not build_dashboard():
            sys.exit(1)
    else:
        if not (STATIC_DIR / "index.html").exists():
            print("Warning: static/index.html not found. Run 'build' first or remove --skip-build.")

    # Start uvicorn
    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.main:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.workers and args.workers > 1:
        uvicorn_cmd += ["--workers", str(args.workers)]

    print(f"Starting server on {args.host}:{args.port}...")

    if IS_WINDOWS:
        # On Windows, use CREATE_NEW_PROCESS_GROUP for clean shutdown
        proc = subprocess.Popen(
            uvicorn_cmd,
            cwd=str(ROOT_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        proc = subprocess.Popen(
            uvicorn_cmd,
            cwd=str(ROOT_DIR),
        )

    _write_pid(proc.pid)
    print(f"Server started (PID {proc.pid}).")
    print(f"  Dashboard: http://{args.host}:{args.port}")
    print(f"  API docs:  http://{args.host}:{args.port}/docs")
    print(f"  PID file:  {PID_FILE}")


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop the running server."""
    port = getattr(args, "port", 8000)
    pid = _read_pid()

    if pid is None:
        # No PID file — try to find process by port
        pid = _find_pid_on_port(port)
        if pid is None:
            print("Server is not running.")
            return
        print(f"No PID file found. Detected server on port {port} (PID {pid}).")

    print(f"Stopping server (PID {pid})...")
    if _kill_pid(pid):
        # Wait for process to exit
        for _ in range(30):
            if not _is_pid_alive(pid):
                break
            time.sleep(0.1)
        else:
            print("Warning: Process did not exit within 3 seconds.")

    PID_FILE.unlink(missing_ok=True)
    if not _is_pid_alive(pid):
        print("Server stopped.")
    else:
        print("Warning: Server may still be running.")


def cmd_restart(args: argparse.Namespace) -> None:
    """Stop then start the server."""
    port = args.port

    # Stop if running
    pid = _read_pid()
    if pid is not None:
        print(f"Stopping server (PID {pid})...")
        _kill_pid(pid)
        for _ in range(30):
            if not _is_pid_alive(pid):
                break
            time.sleep(0.1)
        PID_FILE.unlink(missing_ok=True)
        print("Server stopped.")

    # Ensure port is free before starting
    if not _is_port_free(port):
        print(f"Port {port} is still occupied after stop.")
        if not _free_port(port):
            sys.exit(1)

    # Start
    cmd_start(args)


def cmd_dev(args: argparse.Namespace) -> None:
    """Run backend with --reload and Vite dev server concurrently."""
    processes: list[subprocess.Popen] = []

    # Start uvicorn with --reload
    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.main:app",
        "--reload",
        "--host", args.host,
        "--port", str(args.port),
    ]
    print(f"Starting backend on {args.host}:{args.port} (reload mode)...")
    backend = subprocess.Popen(uvicorn_cmd, cwd=str(ROOT_DIR))
    processes.append(backend)

    # Start Vite dev server
    if DASHBOARD_DIR.exists():
        node_modules = DASHBOARD_DIR / "node_modules"
        if not node_modules.exists():
            print("Installing dashboard dependencies...")
            subprocess.run(
                ["npm", "install"],
                cwd=str(DASHBOARD_DIR),
                shell=IS_WINDOWS,
            )

        print("Starting Vite dev server...")
        vite = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(DASHBOARD_DIR),
            shell=IS_WINDOWS,
        )
        processes.append(vite)
    else:
        print("Warning: dashboard/ not found, skipping Vite dev server.")

    print("\nDev servers running. Press Ctrl+C to stop.\n")

    try:
        # Wait for any process to exit
        while True:
            for proc in processes:
                retcode = proc.poll()
                if retcode is not None:
                    print(f"Process {proc.pid} exited with code {retcode}.")
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down dev servers...")
        for proc in processes:
            if proc.poll() is None:
                if IS_WINDOWS:
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
        # Wait briefly for graceful shutdown
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Dev servers stopped.")


def cmd_status(args: argparse.Namespace) -> None:
    """Check if the server is running."""
    port = getattr(args, "port", 8000)
    pid = _read_pid()

    if pid is not None:
        print(f"Server is running (PID {pid}).")
    else:
        # No PID file — check port
        port_pid = _find_pid_on_port(port)
        if port_pid is not None:
            print(f"No PID file, but port {port} is held by PID {port_pid}.")
            print("  This may be a stale server. Use 'stop' to clean up.")
        elif not _is_port_free(port):
            print(f"No PID file. Port {port} is in use (process could not be identified).")
        else:
            print(f"Server is not running (port {port} is free).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SRG management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = sub.add_parser("start", help="Build dashboard and start server")
    p_start.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_start.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    p_start.add_argument("--skip-build", action="store_true", help="Skip dashboard build")
    p_start.add_argument("--workers", type=int, default=1, help="Number of uvicorn workers")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop the server")
    p_stop.add_argument("--port", type=int, default=8000, help="Port to check if PID file is missing (default: 8000)")
    p_stop.set_defaults(func=cmd_stop)

    # restart
    p_restart = sub.add_parser("restart", help="Restart the server")
    p_restart.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_restart.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    p_restart.add_argument("--skip-build", action="store_true", help="Skip dashboard build")
    p_restart.add_argument("--workers", type=int, default=1, help="Number of uvicorn workers")
    p_restart.set_defaults(func=cmd_restart)

    # dev
    p_dev = sub.add_parser("dev", help="Start backend + Vite dev server")
    p_dev.add_argument("--host", default="0.0.0.0", help="Backend host (default: 0.0.0.0)")
    p_dev.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    p_dev.set_defaults(func=cmd_dev)

    # build
    p_build = sub.add_parser("build", help="Build dashboard only")
    p_build.set_defaults(func=cmd_build)

    # status
    p_status = sub.add_parser("status", help="Check if server is running")
    p_status.add_argument("--port", type=int, default=8000, help="Port to check (default: 8000)")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

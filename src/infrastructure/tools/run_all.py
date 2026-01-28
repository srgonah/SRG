"""
SRG Server Runner - Single command to start the server.

Usage:
    srg-run [--host HOST] [--port PORT] [--no-migrate] [--no-health-check]

This script:
1. Runs database migrations (unless --no-migrate)
2. Starts uvicorn server
3. Verifies health endpoint (unless --no-health-check)
4. Prints useful links
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows-compatible colored output
try:
    import colorama
    colorama.init()
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
except ImportError:
    GREEN = YELLOW = RED = CYAN = RESET = ""


def print_banner() -> None:
    """Print startup banner."""
    print(f"{CYAN}========================================{RESET}")
    print(f"{CYAN}  SRG Server Runner{RESET}")
    print(f"{CYAN}========================================{RESET}")
    print()


def print_success(msg: str) -> None:
    """Print success message."""
    print(f"{GREEN}[OK] {msg}{RESET}")


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"{YELLOW}[..] {msg}{RESET}")


def print_error(msg: str) -> None:
    """Print error message."""
    print(f"{RED}[!!] {msg}{RESET}")


def run_migrations() -> bool:
    """Run database migrations."""
    print_info("Running database migrations...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.infrastructure.storage.sqlite.migrations.migrator"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Migration failed: {result.stderr}")
            return False
        print_success("Migrations complete")
        return True
    except Exception as e:
        print_error(f"Migration error: {e}")
        return False


def check_health(host: str, port: int, timeout: int = 30) -> bool:
    """Check if server health endpoint responds."""
    url = f"http://{host}:{port}/api/health"
    print_info(f"Waiting for server health check ({timeout}s timeout)...")

    start_time = time.time()
    while (time.time() - start_time) < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    print()  # Newline after dots
                    elapsed = round(time.time() - start_time, 1)
                    print_success(f"Health check passed in {elapsed}s")
                    return True
        except (urllib.error.URLError, OSError, Exception):
            # Server not ready yet
            time.sleep(1)  # Slower polling for Windows
            print(".", end="", flush=True)

    print()
    print_error(f"Health check failed after {timeout}s")
    return False


def print_links(host: str, port: int, log_file: str | None) -> None:
    """Print useful links."""
    print()
    print(f"{GREEN}========================================{RESET}")
    print(f"{GREEN}  SRG Server Running{RESET}")
    print(f"{GREEN}========================================{RESET}")
    print()
    print(f"  {CYAN}Swagger UI:{RESET}  http://{host}:{port}/docs")
    print(f"  {CYAN}OpenAPI:{RESET}     http://{host}:{port}/openapi.json")
    print(f"  {CYAN}Health:{RESET}      http://{host}:{port}/api/health")
    print()
    if log_file:
        print(f"  Log file:    {log_file}")
    print("  Stop:        Ctrl+C")
    print()


def main() -> None:
    """Main entry point for srg-run command."""
    parser = argparse.ArgumentParser(
        description="Start SRG server with migrations and health check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  srg-run                    # Start with defaults (127.0.0.1:8000)
  srg-run --port 8080        # Custom port
  srg-run --no-migrate       # Skip migrations
  srg-run --background       # Run in background with log file
        """,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    parser.add_argument(
        "--no-migrate",
        action="store_true",
        help="Skip database migrations",
    )
    parser.add_argument(
        "--no-health-check",
        action="store_true",
        help="Skip health check after startup",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run server in background (Windows: hidden window, logs to server.log)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    args = parser.parse_args()

    print_banner()

    # Step 1: Run migrations
    if not args.no_migrate:
        if not run_migrations():
            sys.exit(1)
    else:
        print_info("Skipping migrations (--no-migrate)")

    # Step 2: Build uvicorn command
    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.api.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")

    log_file = None

    # Step 3: Start server
    if args.background:
        # Background mode: redirect to log file
        log_file = Path("server.log").resolve()
        print_info(f"Starting server in background (logging to {log_file})...")

        # Remove old log file
        if log_file.exists():
            log_file.unlink()

        # Platform-specific background execution
        if sys.platform == "win32":
            # Windows: use CREATE_NO_WINDOW flag
            import subprocess
            DETACHED_PROCESS = 0x00000008  # noqa: N806
            CREATE_NO_WINDOW = 0x08000000  # noqa: N806

            with open(log_file, "w") as log_fh:
                proc = subprocess.Popen(
                    uvicorn_cmd,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                )
            print_success(f"Server started (PID: {proc.pid})")
            print(f"  To stop: taskkill /PID {proc.pid} /F")
        else:
            # Unix: use nohup-style
            with open(log_file, "w") as log_fh:
                proc = subprocess.Popen(
                    uvicorn_cmd,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            print_success(f"Server started (PID: {proc.pid})")
            print(f"  To stop: kill {proc.pid}")

        # Health check for background mode
        if not args.no_health_check:
            time.sleep(3)  # Give server time to start (Windows needs more time)
            if not check_health(args.host, args.port):
                print()
                print_error("Server may have failed to start. Check server.log:")
                try:
                    with open(log_file) as f:
                        lines = f.readlines()
                        for line in lines[-20:]:
                            print(f"  {line.rstrip()}")
                except Exception:
                    pass
                sys.exit(1)

        print_links(args.host, args.port, str(log_file))

    else:
        # Foreground mode: run interactively
        print_info(f"Starting server on {args.host}:{args.port}...")
        print()

        # For foreground, we need to run health check in a thread before exec
        if not args.no_health_check:
            import threading

            def delayed_health_check() -> None:
                time.sleep(2)  # Wait for server to start
                if check_health(args.host, args.port, timeout=30):
                    print_links(args.host, args.port, None)

            health_thread = threading.Thread(target=delayed_health_check, daemon=True)
            health_thread.start()

        # Run uvicorn (this blocks)
        try:
            subprocess.run(uvicorn_cmd)
        except KeyboardInterrupt:
            print()
            print_info("Server stopped")


if __name__ == "__main__":
    main()

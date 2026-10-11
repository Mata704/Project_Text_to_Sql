"""Root helper: `uv run dev.py sync` syncs both apps; `uv run dev.py` runs both."""

import subprocess
import sys

BACKEND = ["uv", "run", "--directory", "backend", "text-to-sql"]
FRONTEND = ["uv", "run", "--directory", "frontend", "streamlit", "run", "app.py"]


def sync() -> int:
    for app in ("backend", "frontend"):
        result = subprocess.run(["uv", "sync", "--directory", app])
        if result.returncode:
            return result.returncode
    return 0


def run() -> int:
    processes = [subprocess.Popen(BACKEND), subprocess.Popen(FRONTEND)]
    try:
        while all(process.poll() is None for process in processes):
            try:
                processes[0].wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "sync":
        return sync()
    if command == "run":
        return run()
    print("Uso: uv run dev.py [sync|run]")
    return 2


if __name__ == "__main__":
    sys.exit(main())

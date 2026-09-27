"""Run on an authorized host with Ollama and Blogger credentials in its environment.

One process owns the queue. No Gemini/Tavily credentials or requests are needed.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import time

import publisher as p


@contextmanager
def queue_lock(state_path):
    # OS releases the lock on process exit/crash; the file is intentionally retained.
    with Path(str(state_path) + ".lock").open("a+b") as file:
        if os.name == "nt":
            import msvcrt
            file.seek(0)
            if not file.read(1):
                file.write(b"0")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)


def configure(state_path):
    p.STATE = Path(state_path).resolve()
    if not p.STATE.is_file():
        raise p.Blocked("Import the latest authoritative state.json before starting the local worker")
    os.environ.update(AI_BACKEND="local", AI_ENABLED="true", AUTO_PUBLISH="true", MAX_STORIES_PER_RUN="1")
    for key in ("GEMINI_API_KEY", "TAVILY_API_KEY", "FREE_TIER_CONFIRMED", "TAVILY_FREE_TIER_CONFIRMED"):
        os.environ.pop(key, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, help="Private persistent copy of latest authoritative queue")
    parser.add_argument("--once", action="store_true", help="Process one batch, then stop")
    args = parser.parse_args()
    configure(args.state)
    with queue_lock(p.STATE):
        while True:
            start = time.monotonic()
            try:
                p.run()
            except (p.Blocked, p.requests.RequestException) as exc:
                print(str(exc) if isinstance(exc, p.Blocked) else type(exc).__name__, flush=True)
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            # Never overlap batches; five-minute checks do not promise five-minute publications.
            time.sleep(max(5, 300 - (time.monotonic() - start)))


if __name__ == "__main__":
    main()

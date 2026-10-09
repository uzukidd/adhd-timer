"""Executable entry point; keep application imports inside their package."""

import sys

from focus_flow.app import main


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from smoke_check import run

        raise SystemExit(run(sys.argv[2]))
    raise SystemExit(main())

"""Launch Focus Flow independently of the working directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from focus_flow.app import main

if __name__ == "__main__":
    raise SystemExit(main())

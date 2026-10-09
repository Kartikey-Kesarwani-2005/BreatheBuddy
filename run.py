"""BreatheBuddy launcher.

    python run.py            # start the API + dashboard on http://localhost:8000
    python run.py --demo     # run the CLI demo (all acceptance criteria)
    python run.py --port 9000

No third-party packages are required for the default path.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Make ``src`` importable without installation.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="BreatheBuddy")
    parser.add_argument("--demo", action="store_true", help="run the CLI demo")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:  # keep em dashes printable on Windows consoles
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.demo:
        from breathebuddy.demo import main as demo_main
        demo_main()
        return

    from breathebuddy.api import serve
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

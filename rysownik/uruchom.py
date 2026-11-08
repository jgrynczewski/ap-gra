"""Runs the drawing code of the AI and saves the frames - in its own process,
started by rysownik/serwis.py with limits of memory and time:

    python -I rysownik/uruchom.py kod.py klatki/

On an error: the traceback of the drawing code to stderr, exit code 1.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rysownik.klatki import render  # noqa: E402

CODE_FILE = "rysunek.py"  # the name in tracebacks


def main(code_path: str, out: str) -> int:
    code = Path(code_path).read_text(encoding="utf-8")
    namespace = {"__name__": "rysunek"}
    try:
        exec(compile(code, CODE_FILE, "exec"), namespace)  # noqa: S102 - the point of this process
        render(namespace["rysuj"], Path(out))
    except Exception:  # noqa: BLE001 - every error goes back to the AI
        # Only what concerns the drawing code: frames of our files (and their
        # source lines) are left out
        shown, skipping = [], False
        for line in traceback.format_exc().splitlines():
            if line.startswith("  File "):
                skipping = CODE_FILE not in line
            elif not (skipping and line.startswith("    ")):
                skipping = False
            if not skipping:
                shown.append(line)
        print("\n".join(shown[-30:]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

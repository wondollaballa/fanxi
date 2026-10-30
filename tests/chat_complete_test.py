"""Compile and run the host C unit tests for the chat line's command work.

  * tests/chat_complete_test.c against host/addons/complete.c: the completion table, the
    argument syntax //help prints, and its colouring.
  * tests/typeahead_test.c against complete.c and typeahead.c: the //hint suggestion the input
    line carries.

Both are host C, not Python, so this builds them with the system C compiler and runs their
assertions.  It needs no game files, SDL or FFXI checkout.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc")

PROGRAMS = (
    ("chat_complete_test", ("host/addons/complete.c", "tests/chat_complete_test.c")),
    ("typeahead_test", ("host/addons/complete.c", "host/addons/typeahead.c", "tests/typeahead_test.c")),
)


def build_and_run(folder: Path, name: str, sources: tuple[str, ...]) -> int:
    exe = folder / name
    command = [CC, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "host" / "addons")]
    command += [str(ROOT / source) for source in sources]
    command += ["-o", str(exe)]
    try:
        subprocess.run(command, check=True, cwd=ROOT)
    except FileNotFoundError:
        print("%s: SKIP (no C compiler: %s)" % (name, CC))
        return 0
    except subprocess.CalledProcessError as exc:
        print("%s: FAIL (compile error %s)" % (name, exc.returncode))
        return 1
    return subprocess.run([str(exe)], cwd=ROOT).returncode


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chatcomplete.") as folder:
        status = 0
        for name, sources in PROGRAMS:
            status |= build_and_run(Path(folder), name, sources)
        return status


if __name__ == "__main__":
    sys.exit(main())

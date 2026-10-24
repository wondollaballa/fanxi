"""Compile and run tests/chat_complete_test.c against host/addons/complete.c.

The completion table is host C, not Python, so this test builds the one source file with the
system C compiler and runs its assertions.  It needs no game files, SDL or FFXI checkout.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chatcomplete.") as folder:
        exe = Path(folder) / "chat_complete_test"
        command = [
            CC,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "host" / "addons"),
            str(ROOT / "host" / "addons" / "complete.c"),
            str(ROOT / "tests" / "chat_complete_test.c"),
            "-o",
            str(exe),
        ]
        try:
            subprocess.run(command, check=True, cwd=ROOT)
        except FileNotFoundError:
            print("chat_complete_test: SKIP (no C compiler: %s)" % CC)
            return 0
        except subprocess.CalledProcessError as exc:
            print("chat_complete_test: FAIL (compile error %s)" % exc.returncode)
            return 1
        result = subprocess.run([str(exe)], cwd=ROOT)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())

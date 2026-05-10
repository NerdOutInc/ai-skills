#!/usr/bin/env python3
"""Ensure cliclick is installed and print the executable path."""

from __future__ import annotations

import argparse
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def find_executable(name: str, extras: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extras or []:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def find_brew() -> str | None:
    found = shutil.which("brew")
    if found:
        return found
    for candidate in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")):
        if candidate.exists():
            return str(candidate)
    return None


def install_cliclick(no_install: bool) -> str:
    cliclick = find_executable(
        "cliclick",
        [Path("/opt/homebrew/bin/cliclick"), Path("/usr/local/bin/cliclick")],
    )
    if cliclick:
        return cliclick

    install_cmd = "brew install cliclick"
    if no_install:
        raise SystemExit(
            f"Missing cliclick. Install it with:\n  {install_cmd}\n"
            "Then rerun this command, or rerun without --no-install on macOS with Homebrew."
        )
    if platform.system() != "Darwin":
        raise SystemExit(
            "Missing cliclick. Automatic install is only supported on macOS with Homebrew.\n"
            f"Install it with:\n  {install_cmd}"
        )

    brew = find_brew()
    if not brew:
        raise SystemExit(
            "Missing cliclick. Homebrew was not found, so automatic install is unavailable.\n"
            f"Install it with:\n  {install_cmd}"
        )

    cmd = [brew, "install", "cliclick"]
    eprint(f"+ {shlex.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, stdout=sys.stderr)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Automatic cliclick install failed. Try:\n  {install_cmd}") from exc

    cliclick = find_executable(
        "cliclick",
        [Path("/opt/homebrew/bin/cliclick"), Path("/usr/local/bin/cliclick")],
    )
    if cliclick:
        return cliclick
    raise SystemExit("cliclick install completed, but cliclick still was not found on PATH.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-install", action="store_true", help="Do not install cliclick automatically")
    args = parser.parse_args()

    print(install_cliclick(args.no_install))
    return 0


if __name__ == "__main__":
    sys.exit(main())

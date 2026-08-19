#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark - the state a build is measured from
#
# Puts the tree into the state a turnaround measurement starts from and then
# runs the command, so that the preparation belongs to every repeat rather than
# being something done once before the first of them.
#
# Two states are needed:
#
#   --remove   nothing built - a checkout that has never been simulated
#   --touch    a testbench that has just been edited and saved
#
# The edit is modelled rather than made. Moving a file's timestamp on is what
# saving it does as far as every build tool is concerned - make compares mtimes,
# and Python compares the mtime recorded in the .pyc header - while which
# variant of the testbench is built is chosen by a define instead. So the
# rebuild is a real rebuild of genuinely different source, and nothing in the
# tree is rewritten or left behind.
#
# A timestamp alone is not enough to make it one. Verilator hashes what it is
# given and skips regenerating an identical model, quite rightly, so repeating
# the same edit would be measured once and then skipped twice - and the median
# of three would be a build that did nothing. --revision is what makes each one
# a real edit: a number that differs every invocation, which the testbench
# carries as a constant, so the second edit is as much of an edit as the first.
#
# The command replaces this process rather than being spawned from it, so that
# the timing harness measuring the process group sees exactly what it would have
# seen had it run the command itself.


from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the state a build is measured from, then run a command."
    )
    parser.add_argument("--remove", nargs="*", type=Path, default=[], metavar="PATH",
                        help="Build products to throw away - what makes a build cold")
    parser.add_argument("--touch", nargs="*", type=Path, default=[], metavar="FILE",
                        help="Testbench sources to mark as just edited")
    parser.add_argument("--revision", metavar="NAME",
                        help="Environment variable to set to a number that differs every "
                             "invocation - which variant of the edited testbench to build")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command to run")
    args = parser.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        parser.error("no command given - separate it from the options with --")

    for path in args.remove:
        remove(path)

    for path in args.touch:
        # An edit to a file that is not there would be measured as a build with
        # nothing to rebuild, which is precisely the wrong answer.
        if not path.exists():
            print(f"bench_edit: nothing to edit at {path}", file=sys.stderr)
            return 1
        path.touch()

    if args.revision:
        # The process id: different for every invocation, because the one before
        # it was this process's parent's child and the kernel does not hand the
        # same number back that quickly. Nothing reads it as a count - all that
        # is asked of it is that this edit is not last time's edit.
        os.environ[args.revision] = str(os.getpid())

    try:
        os.execvp(cmd[0], cmd)
    except OSError as e:
        print(f"bench_edit: cannot run {cmd[0]} : {e.strerror}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())

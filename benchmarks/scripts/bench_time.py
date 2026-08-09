#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark Timing Harness
#
# Runs a command a number of times and records real time, user time, system time
# and CPU usage for each run as a row in a CSV file.
#
# The measurement is process *tree* aware. This matters because SystemVerilog
# simulators solve constraints in a separate SMT solver process (Verilator talks
# to "z3 --in" over a pipe, for example). That child is never reaped by the
# simulator, so its CPU time is invisible to getrusage()/"/usr/bin/time" and the
# SystemVerilog flavour would appear to use no CPU at all.
#
# Two independent measurements are therefore taken and combined:
#   1. getrusage(RUSAGE_CHILDREN) around the run - exact, but only covers
#      descendants that were waited for.
#   2. Sampling /proc/<pid>/stat for every process in the command's process
#      group - covers everything, but can miss the last few ticks of a process
#      that dies between samples.
# The larger of the two is reported for each of user and system time.


from __future__ import annotations

import argparse
import csv
import os
import resource
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
PAGE_SIZE_KB = os.sysconf("SC_PAGE_SIZE") // 1024

FIELDS = [
    "benchmark",
    "flavour",
    "tool",
    "phase",
    "iterations",
    "repeat",
    "real_s",
    "user_s",
    "sys_s",
    "cpu_pct",
    "max_rss_kb",
    "status",
]


class TreeSampler(threading.Thread):
    """Sample the CPU time and RSS of every process in a process group."""

    # /proc/<pid>/stat fields, indexed from field 3 (state) - i.e. after the
    # "<pid> (<comm>)" prefix which is skipped because comm may contain spaces.
    PGRP = 2
    UTIME = 11
    STIME = 12
    RSS = 21

    def __init__(self, pgid: int, interval: float = 0.02) -> None:
        super().__init__(daemon=True)
        self._pgid = pgid
        self._interval = interval
        self._done = threading.Event()
        # pid -> (peak utime_s, peak stime_s, peak rss_kb)
        self._peaks: dict[int, tuple[float, float, int]] = {}

    def sample(self) -> None:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit():
                continue

            try:
                with open(f"/proc/{entry.name}/stat", "rb") as f:
                    data = f.read()
            except OSError:
                # Process exited while being read - nothing more to learn.
                continue

            # comm is wrapped in parentheses and may contain anything.
            close = data.rfind(b")")
            if close < 0:
                continue

            fields = data[close + 2:].split()
            try:
                if int(fields[self.PGRP]) != self._pgid:
                    continue
                utime = int(fields[self.UTIME]) / CLOCK_TICKS
                stime = int(fields[self.STIME]) / CLOCK_TICKS
                rss = int(fields[self.RSS]) * PAGE_SIZE_KB
            except (IndexError, ValueError):
                continue

            pid = int(entry.name)
            peak = self._peaks.get(pid, (0.0, 0.0, 0))
            # Per process counters are monotonic, so the last value seen is the
            # best estimate of the total for a process that has since exited.
            self._peaks[pid] = (max(peak[0], utime), max(peak[1], stime), max(peak[2], rss))

    def run(self) -> None:
        while not self._done.is_set():
            self.sample()
            self._done.wait(self._interval)

    def stop(self) -> None:
        self._done.set()
        self.join(timeout=5.0)
        # One last look, to catch anything that ran since the final sample.
        self.sample()

    @property
    def totals(self) -> tuple[float, float, int]:
        user = sum(p[0] for p in self._peaks.values())
        system = sum(p[1] for p in self._peaks.values())
        rss = sum(p[2] for p in self._peaks.values())
        return (user, system, rss)


def measure(cmd: list[str], log: os.PathLike | None, interval: float) -> dict:
    """Run cmd once and return its resource usage."""
    logfile = open(log, "ab") if log is not None else subprocess.DEVNULL

    try:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=logfile,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as e:
            return {"real_s": 0.0, "user_s": 0.0, "sys_s": 0.0, "cpu_pct": 0.0,
                    "max_rss_kb": 0, "status": f"error:{e.strerror}"}

        sampler = TreeSampler(os.getpgid(proc.pid), interval)
        sampler.start()

        returncode = proc.wait()

        real = time.monotonic() - start
        sampler.stop()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
    finally:
        if logfile is not subprocess.DEVNULL:
            logfile.close()

    tree_user, tree_sys, tree_rss = sampler.totals
    user = max(after.ru_utime - before.ru_utime, tree_user)
    system = max(after.ru_stime - before.ru_stime, tree_sys)
    rss = max(after.ru_maxrss, tree_rss)

    return {
        "real_s": round(real, 4),
        "user_s": round(user, 4),
        "sys_s": round(system, 4),
        "cpu_pct": round(100.0 * (user + system) / real, 1) if real > 0 else 0.0,
        "max_rss_kb": int(rss),
        "status": "ok" if returncode == 0 else f"exit:{returncode}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Time a benchmark command and append the result to a CSV file."
    )
    parser.add_argument("--csv", type=Path, required=True, help="CSV file to append results to")
    parser.add_argument("--log", type=Path, default=None, help="File to capture command output in")
    parser.add_argument("--benchmark", default="unknown", help="Name of the benchmark")
    parser.add_argument("--flavour", default="unknown", help="Testbench flavour (sv / avl)")
    parser.add_argument("--tool", default="unknown", help="Tool used to run the testbench")
    parser.add_argument("--phase", default="run", help="Phase being measured (run / baseline)")
    parser.add_argument("--iterations", type=int, default=0, help="Randomizations per run")
    parser.add_argument("--repeats", type=int, default=1, help="Number of times to run the command")
    parser.add_argument("--warmup", type=int, default=0, help="Untimed runs before measuring")
    parser.add_argument("--interval", type=float, default=0.02, help="Sample interval in seconds")
    parser.add_argument("--quiet", action="store_true", help="Do not print results to stdout")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command to run")
    args = parser.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        parser.error("no command given - separate it from the options with --")

    if shutil.which(cmd[0]) is None and not Path(cmd[0]).exists():
        print(f"bench_time: command not found : {cmd[0]}", file=sys.stderr)
        return 127

    if args.log is not None:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_bytes(b"")

    for _ in range(args.warmup):
        measure(cmd, args.log, args.interval)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    new = not args.csv.exists() or args.csv.stat().st_size == 0

    failures = 0
    reals = []
    with open(args.csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            writer.writeheader()

        for repeat in range(args.repeats):
            result = measure(cmd, args.log, args.interval)
            row = {
                "benchmark": args.benchmark,
                "flavour": args.flavour,
                "tool": args.tool,
                "phase": args.phase,
                "iterations": args.iterations,
                "repeat": repeat,
                **result,
            }
            writer.writerow(row)
            f.flush()

            reals.append(result["real_s"])
            if result["status"] != "ok":
                failures += 1

            if not args.quiet:
                print(
                    f"  {args.flavour:4s} {args.phase:8s} run {repeat + 1}/{args.repeats} : "
                    f"real {result['real_s']:8.3f}s  user {result['user_s']:8.3f}s  "
                    f"sys {result['sys_s']:7.3f}s  cpu {result['cpu_pct']:6.1f}%  "
                    f"{result['status']}"
                )

    if failures and not args.quiet:
        print(
            f"  {args.flavour} {args.phase} : {failures}/{args.repeats} run(s) failed"
            f" - see {args.log}",
            file=sys.stderr,
        )
    elif reals and not args.quiet and args.repeats > 1:
        print(f"  {args.flavour:4s} {args.phase:8s} median   : real {statistics.median(reals):8.3f}s")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

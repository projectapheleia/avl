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
#   2. Sampling every process in the command's process group - covers
#      everything, but can miss the last few ticks of a process that dies
#      between samples.
# The larger of the two is reported for each of user and system time.
#
# The second measurement has no portable interface, so there is one sampler per
# platform: Linux reads /proc/<pid>/stat, macOS asks libproc. Anywhere else the
# run still measures, through getrusage alone.


from __future__ import annotations

import argparse
import csv
import ctypes
import ctypes.util
import os
import resource
import shutil
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from pathlib import Path

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
PAGE_SIZE_KB = os.sysconf("SC_PAGE_SIZE") // 1024

# getrusage reports the peak resident set in kilobytes on Linux and in bytes on
# macOS. Everything here is in kilobytes.
RUSAGE_RSS_DIVISOR = 1024 if sys.platform == "darwin" else 1

FIELDS = [
    "benchmark",
    "flavour",
    "tool",
    "phase",
    "unit",
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
    """Sample the CPU time and RSS of every process in a process group.

    Subclassed per platform - all a subclass provides is snapshot(). The
    bookkeeping is common: the per process counters are monotonic, so the
    highest value seen for a process is the best estimate of what it finished
    with, whether or not it was still alive at the final sample.
    """

    def __init__(self, pgid: int, interval: float = 0.02) -> None:
        super().__init__(daemon=True)
        self._pgid = pgid
        self._interval = interval
        self._done = threading.Event()
        # pid -> (peak utime_s, peak stime_s, peak rss_kb)
        self._peaks: dict[int, tuple[float, float, int]] = {}

    def snapshot(self) -> Iterable[tuple[int, float, float, int]]:
        """(pid, user_s, system_s, rss_kb) for each process in the group."""
        raise NotImplementedError

    def sample(self) -> None:
        for pid, utime, stime, rss in self.snapshot():
            peak = self._peaks.get(pid, (0.0, 0.0, 0))
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


class ProcSampler(TreeSampler):
    """Linux - every process is a directory under /proc."""

    # /proc/<pid>/stat fields, indexed from field 3 (state) - i.e. after the
    # "<pid> (<comm>)" prefix which is skipped because comm may contain spaces.
    PGRP = 2
    UTIME = 11
    STIME = 12
    RSS = 21

    def snapshot(self) -> Iterable[tuple[int, float, float, int]]:
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
                yield (
                    int(entry.name),
                    int(fields[self.UTIME]) / CLOCK_TICKS,
                    int(fields[self.STIME]) / CLOCK_TICKS,
                    int(fields[self.RSS]) * PAGE_SIZE_KB,
                )
            except (IndexError, ValueError):
                continue


class TaskInfo(ctypes.Structure):
    """macOS struct proc_taskinfo, from <sys/proc_info.h>."""

    _fields_ = [
        ("pti_virtual_size", ctypes.c_uint64),
        ("pti_resident_size", ctypes.c_uint64),
        ("pti_total_user", ctypes.c_uint64),
        ("pti_total_system", ctypes.c_uint64),
        ("pti_threads_user", ctypes.c_uint64),
        ("pti_threads_system", ctypes.c_uint64),
    ] + [(f"pti_int_{i}", ctypes.c_int32) for i in range(12)]


class TimebaseInfo(ctypes.Structure):
    """macOS struct mach_timebase_info, from <mach/mach_time.h>."""

    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


class LibprocSampler(TreeSampler):
    """macOS - there is no /proc, so ask libproc for the same figures.

    proc_pidinfo reports CPU time in mach absolute time units rather than in
    nanoseconds, and the two differ: on Apple silicon a unit is 125/3 ns. The
    timebase is read once and applied to every sample.
    """

    PROC_PIDTASKINFO = 4

    def __init__(self, pgid: int, interval: float = 0.02) -> None:
        super().__init__(pgid, interval)
        self._lib = load_libproc()
        self._scale = mach_timebase() / 1e9
        self._pids = (ctypes.c_int32 * 4096)()

    def snapshot(self) -> Iterable[tuple[int, float, float, int]]:
        # Older releases return a byte count here and newer ones a pid count.
        # Reading it as a pid count is right for the latter and generous for the
        # former, and every entry is checked below, so either way nothing in the
        # group is missed.
        count = self._lib.proc_listpgrppids(self._pgid, ctypes.byref(self._pids),
                                            ctypes.sizeof(self._pids))
        if count <= 0:
            return

        if count >= len(self._pids):
            # A process group larger than the buffer. Grow it for next time and
            # take what was returned in the meantime.
            self._pids = (ctypes.c_int32 * (2 * len(self._pids)))()

        info = TaskInfo()
        size = ctypes.sizeof(info)
        for index in range(min(count, len(self._pids))):
            pid = self._pids[index]
            if pid <= 0:
                continue

            try:
                if os.getpgid(pid) != self._pgid:
                    continue
            except OSError:
                # Exited, or not ours to ask about.
                continue

            if self._lib.proc_pidinfo(pid, self.PROC_PIDTASKINFO, 0,
                                      ctypes.byref(info), size) != size:
                continue

            yield (
                pid,
                info.pti_total_user * self._scale,
                info.pti_total_system * self._scale,
                info.pti_resident_size // 1024,
            )


class NullSampler(TreeSampler):
    """Neither /proc nor libproc - getrusage has to stand on its own."""

    def snapshot(self) -> Iterable[tuple[int, float, float, int]]:
        return ()


def load_libproc() -> ctypes.CDLL:
    """libproc, with the two entry points the sampler uses declared."""
    lib = ctypes.CDLL(ctypes.util.find_library("proc") or "libproc.dylib", use_errno=True)

    lib.proc_listpgrppids.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
    lib.proc_listpgrppids.restype = ctypes.c_int
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                 ctypes.c_void_p, ctypes.c_int]
    lib.proc_pidinfo.restype = ctypes.c_int

    return lib


def mach_timebase() -> float:
    """Nanoseconds per mach absolute time unit."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    timebase = TimebaseInfo()
    if libc.mach_timebase_info(ctypes.byref(timebase)) != 0 or not timebase.denom:
        return 1.0
    return timebase.numer / timebase.denom


def make_sampler(pgid: int, interval: float) -> TreeSampler:
    """The sampler this platform can support."""
    if os.path.isdir("/proc"):
        return ProcSampler(pgid, interval)

    if sys.platform == "darwin":
        try:
            return LibprocSampler(pgid, interval)
        except (OSError, AttributeError):  # pragma: no cover - libproc is always there
            pass

    return NullSampler(pgid, interval)


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

        sampler = make_sampler(os.getpgid(proc.pid), interval)
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
    rss = max(after.ru_maxrss / RUSAGE_RSS_DIVISOR, tree_rss)

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
    parser.add_argument("--flavour", default="unknown",
                        help="Testbench flavour (sv / avl / pyuvm)")
    parser.add_argument("--tool", default="unknown", help="Tool used to run the testbench")
    parser.add_argument("--phase", default="run", help="Phase being measured (run / baseline)")
    parser.add_argument("--unit", default="randomization",
                        help="What one iteration of this benchmark is, in the singular - the "
                             "word the report is written in")
    parser.add_argument("--iterations", type=int, default=0, help="Iterations per run")
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
                "unit": args.unit,
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
                    f"  {args.flavour:6s} {args.phase:8s} run {repeat + 1}/{args.repeats} : "
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
        print(f"  {args.flavour:6s} {args.phase:8s} median   : real {statistics.median(reals):8.3f}s")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

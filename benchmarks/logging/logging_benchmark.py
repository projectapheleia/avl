#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) logging benchmark.
#
# Measures what it costs a testbench to write a log message. The testbench
# (cocotb/benchmark.py) logs N times in each of several ways and times each loop
# in-process; this script runs the simulation R times and aggregates.
#
# Measurements:
#
#   info        - one INFO message from a component, no log file. The common case
#   info_deep   - the same from a six deep hierarchy, where the group name that
#                 identifies the component costs more to build
#   filtered    - a DEBUG message, below the level, which should cost almost nothing
#   formatted   - an INFO message built from an f-string, as most real ones are
#   log_api     - straight through avl.Log, without a component to name the group
#   to_file_*   - with a log file set, in each of three formats
#
# "info" is the headline figure.
#
# Usage:
#   source ./avl.sh            # from the repo root, sets up SIM, venv, AVL_ROOT
#   cd benchmarks/logging
#   ./logging_benchmark.py                     # 2000 messages, 3 repeats
#   ./logging_benchmark.py -n 5000 -r 5
#   ./logging_benchmark.py --json base.json --label base
#   ./logging_benchmark.py --compare base.json # regression report

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

MARKER = "AVL_BENCH_JSON "

ORDER = [
    ("info", "info from a component"),
    ("info_deep", "info, six deep hierarchy"),
    ("filtered", "below the level"),
    ("formatted", "formatted message"),
    ("log_api", "avl.Log directly"),
    ("to_file_csv", "to a .csv log file"),
    ("to_file_json", "to a .json log file"),
    ("to_file_txt", "to a .txt log file"),
]

HEADLINE = "info"


class Result:
    """Per-message timing samples for a single measurement, in seconds."""

    def __init__(self, name: str, description: str, samples: list[float]) -> None:
        self.name = name
        self.description = description
        self.samples = samples

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples)

    @property
    def best(self) -> float:
        return min(self.samples)

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "samples": self.samples,
            "mean": self.mean,
            "best": self.best,
            "stdev": self.stdev,
        }


def run_once(n: int, sim: str) -> dict[str, float]:
    """Run the testbench once and return its per-message timings."""
    (HERE / "results.xml").unlink(missing_ok=True)
    env = dict(os.environ, AVL_BENCH_N=str(n))
    proc = subprocess.run(
        ["make", "--no-print-directory", "MODULE=benchmark", f"SIM={sim}"],
        cwd=HERE, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"simulation failed ({proc.returncode})")

    for line in proc.stdout.splitlines():
        idx = line.find(MARKER)
        if idx >= 0:
            return json.loads(line[idx + len(MARKER):])
    sys.stderr.write(proc.stdout)
    raise SystemExit("benchmark produced no results - is the testbench importing avl?")


def fmt_us(seconds: float) -> str:
    return f"{seconds * 1e6:8.2f}"


def report(results: dict[str, Result], n: int, repeats: int, sim: str,
           label: str | None) -> None:
    width = 74
    print()
    print("=" * width)
    title = "AVL logging benchmark"
    if label:
        title += f" [{label}]"
    print(title)
    print("=" * width)
    print(f"simulator      : {sim}")
    print(f"messages       : {n} per measurement")
    print(f"repeats        : {repeats}")
    print(f"python         : {sys.version.split()[0]}")
    try:
        import avl

        print(f"avl version    : {getattr(avl, '__version__', 'unknown')}")
    except Exception:  # pragma: no cover - diagnostics only
        pass
    print("-" * width)
    print(f"{'measurement':<32}{'mean (us)':>12}{'best (us)':>12}{'stdev (us)':>12}")
    print("-" * width)
    for name, description in ORDER:
        r = results.get(name)
        if r is None:
            continue
        prefix = "* " if name == HEADLINE else "  "
        print(f"{prefix + description:<32}{fmt_us(r.mean):>12}"
              f"{fmt_us(r.best):>12}{fmt_us(r.stdev):>12}")
    print("-" * width)
    head = results[HEADLINE]
    print(f"{'* per message':<32}{fmt_us(head.mean):>12}"
          f"{'  ' + f'{head.mean * n * 1000:.1f} ms per {n}':>24}")
    print("=" * width)
    print()


def compare(results: dict[str, Result], previous: dict) -> None:
    width = 74
    prev_label = previous.get("label") or "previous"
    prev_results = previous["results"]
    print("=" * width)
    print(f"Comparison against '{prev_label}'")
    print("=" * width)
    print(f"{'measurement':<28}{prev_label[:9]:>11}{'now':>11}{'delta':>11}{'change':>11}")
    print("-" * width)
    for name, description in ORDER:
        r = results.get(name)
        if r is None or name not in prev_results:
            continue
        old = prev_results[name]["mean"]
        new = r.mean
        delta = new - old
        pct = 100.0 * delta / old if old else 0.0
        print(f"{description[:27]:<28}{fmt_us(old):>11}{fmt_us(new):>11}"
              f"{fmt_us(delta):>11}{pct:>10.1f}%")
    print("=" * width)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure AVL logging cost.")
    parser.add_argument("-n", "--messages", type=int, default=2000,
                        help="messages per measurement (default: 2000)")
    parser.add_argument("-r", "--repeats", type=int, default=3,
                        help="times to repeat the whole simulation (default: 3)")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--json", metavar="FILE", help="write the raw results to FILE")
    parser.add_argument("--label", help="label recorded with --json and shown in reports")
    parser.add_argument("--compare", metavar="FILE",
                        help="compare these results against a previously saved --json file")
    args = parser.parse_args()

    if args.messages < 1:
        parser.error("--messages must be >= 1")
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    samples: dict[str, list[float]] = {}
    for i in range(args.repeats):
        print(f"run {i + 1}/{args.repeats} ...", flush=True)
        for name, value in run_once(args.messages, args.sim).items():
            samples.setdefault(name, []).append(value)

    descriptions = dict(ORDER)
    results = {name: Result(name, descriptions.get(name, name), values)
               for name, values in samples.items()}

    report(results, args.messages, args.repeats, args.sim, args.label)

    if args.json:
        payload = {
            "label": args.label,
            "messages": args.messages,
            "repeats": args.repeats,
            "sim": args.sim,
            "python": sys.version.split()[0],
            "results": {name: r.as_dict() for name, r in results.items()},
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"results written to {args.json}")

    if args.compare:
        compare(results, json.loads(Path(args.compare).read_text()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

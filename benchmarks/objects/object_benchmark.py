#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) object and variable creation benchmark.
#
# Measures how long it takes to construct AVL objects and variables. The
# testbench (cocotb/benchmark.py) builds N of each, cycling through several
# distinct transaction classes, and times each loop in-process; this script runs
# the simulation R times and aggregates.
#
# Measurements:
#
#   object       - a bare avl.Object
#   transaction  - a bare avl.Transaction
#   var_*        - a single variable of each type (logic, uint, int, bool,
#                  enum, float)
#   frame        - a transaction carrying one of each variable type
#   mixed        - four different transaction classes, round-robin
#
# "frame" is the headline figure: the cost of one realistic transaction.
#
# Usage:
#   source ./avl.sh            # from the repo root, sets up SIM, venv, AVL_ROOT
#   cd benchmarks/objects
#   ./object_benchmark.py                          # 1000 objects, 3 repeats
#   ./object_benchmark.py -n 10000 -r 5
#   ./object_benchmark.py --json base.json --label base
#   ./object_benchmark.py --compare base.json      # regression report

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
    ("object", "avl.Object"),
    ("transaction", "avl.Transaction"),
    ("var_logic", "avl.Logic (64 bit)"),
    ("var_uint", "avl.Uint32"),
    ("var_int", "avl.Int16"),
    ("var_bool", "avl.Bool"),
    ("var_enum", "avl.Enum"),
    ("var_float", "avl.Fp32"),
    ("frame", "transaction, 6 variables"),
    ("mixed", "4 classes, round-robin"),
]

HEADLINE = "frame"


class Result:
    """Per-object timing samples for a single measurement, in seconds."""

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
    """Run the testbench once and return its per-object timings."""
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
    title = "AVL object creation benchmark"
    if label:
        title += f" [{label}]"
    print(title)
    print("=" * width)
    print(f"simulator      : {sim}")
    print(f"objects        : {n} per measurement")
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
    print(f"{'* per transaction':<32}{fmt_us(head.mean):>12}"
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
        description="Measure AVL object and variable creation cost.")
    parser.add_argument("-n", "--objects", type=int, default=1000,
                        help="objects to create per measurement (default: 1000)")
    parser.add_argument("-r", "--repeats", type=int, default=3,
                        help="times to repeat the whole simulation (default: 3)")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--json", metavar="FILE", help="write the raw results to FILE")
    parser.add_argument("--label", help="label recorded with --json and shown in reports")
    parser.add_argument("--compare", metavar="FILE",
                        help="compare these results against a previously saved --json file")
    args = parser.parse_args()

    if args.objects < 1:
        parser.error("--objects must be >= 1")
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    samples: dict[str, list[float]] = {}
    for i in range(args.repeats):
        print(f"run {i + 1}/{args.repeats} ...", flush=True)
        for name, value in run_once(args.objects, args.sim).items():
            samples.setdefault(name, []).append(value)

    descriptions = dict(ORDER)
    results = {name: Result(name, descriptions.get(name, name), values)
               for name, values in samples.items()}

    report(results, args.objects, args.repeats, args.sim, args.label)

    if args.json:
        payload = {
            "label": args.label,
            "objects": args.objects,
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

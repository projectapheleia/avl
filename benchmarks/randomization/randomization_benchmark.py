#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) randomization benchmark.
#
# Measures how long it takes to randomize a constrained transaction. The
# testbench (cocotb/benchmark.py) randomizes N times and times each loop
# in-process; this script runs the simulation R times and aggregates.
#
# Measurements:
#
#   constrained   - a packet with arithmetic, bitwise and select constraints
#                   over logic, uint, int, enum and float variables, its fields
#                   left most of their range
#   tightly_constrained - the same variable types held to narrow ranges, as a
#                   real testbench usually holds them
#   integer_only  - the same shape without the floating point variable
#   unconstrained - the same variables with no constraints, the floor
#   fresh_object  - a new packet built and randomized each time, as a sequence
#                   generating items would
#   single_var    - one variable randomized on its own
#
# "constrained" is the headline figure.
#
# Usage:
#   source ./avl.sh            # from the repo root, sets up SIM, venv, AVL_ROOT
#   cd benchmarks/randomization
#   ./randomization_benchmark.py                     # 1000 randomizations, 3 repeats
#   ./randomization_benchmark.py -n 5000 -r 5
#   ./randomization_benchmark.py --json base.json --label base
#   ./randomization_benchmark.py --compare base.json # regression report

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
    ("constrained", "constrained packet"),
    ("tightly_constrained", "tightly constrained packet"),
    ("integer_only", "integer fields only"),
    ("unconstrained", "no constraints"),
    ("fresh_object", "new object each time"),
    ("single_var", "single variable"),
]

HEADLINE = "constrained"


class Result:
    """Per-randomization timing samples for a single measurement, in seconds."""

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
    """Run the testbench once and return its per-randomization timings."""
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
    title = "AVL randomization benchmark"
    if label:
        title += f" [{label}]"
    print(title)
    print("=" * width)
    print(f"simulator      : {sim}")
    print(f"randomizations : {n} per measurement")
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
    print(f"{'* per randomization':<32}{fmt_us(head.mean):>12}"
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
        description="Measure AVL randomization cost.")
    parser.add_argument("-n", "--randomizations", type=int, default=1000,
                        help="randomizations per measurement (default: 1000)")
    parser.add_argument("-r", "--repeats", type=int, default=3,
                        help="times to repeat the whole simulation (default: 3)")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--json", metavar="FILE", help="write the raw results to FILE")
    parser.add_argument("--label", help="label recorded with --json and shown in reports")
    parser.add_argument("--compare", metavar="FILE",
                        help="compare these results against a previously saved --json file")
    args = parser.parse_args()

    if args.randomizations < 1:
        parser.error("--randomizations must be >= 1")
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    samples: dict[str, list[float]] = {}
    for i in range(args.repeats):
        print(f"run {i + 1}/{args.repeats} ...", flush=True)
        for name, value in run_once(args.randomizations, args.sim).items():
            samples.setdefault(name, []).append(value)

    descriptions = dict(ORDER)
    results = {name: Result(name, descriptions.get(name, name), values)
               for name, values in samples.items()}

    report(results, args.randomizations, args.repeats, args.sim, args.label)

    if args.json:
        payload = {
            "label": args.label,
            "randomizations": args.randomizations,
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

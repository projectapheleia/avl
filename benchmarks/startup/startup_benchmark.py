#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) start-up benchmark.
#
# Measures how long it takes to start an AVL testbench and reports the overhead
# AVL adds on top of a bare cocotb testbench.
#
# Four quantities are measured, each in a fresh process, N times (default 3):
#
#   import     - "import avl" in a clean interpreter. Pure library import cost.
#   avl_import - "import avl" with cocotb already loaded, timed inside the child
#                process. Isolates AVL's own import cost, as a simulator sees it.
#   baseline   - a full simulator run of a plain cocotb testbench (cocotb/baseline.py).
#   benchmark  - a full simulator run of the equivalent AVL testbench
#                (cocotb/benchmark.py), which builds a standard avl.Env and nothing else.
#
# The reported overhead is (benchmark - baseline): everything AVL costs to start,
# with the simulator, make and cocotb costs cancelled out.
#
# Usage:
#   source ./avl.sh            # from the repo root, sets up SIM, venv, AVL_ROOT
#   cd benchmarks/startup
#   ./startup_benchmark.py                       # 3 iterations
#   ./startup_benchmark.py -n 10                 # 10 iterations
#   ./startup_benchmark.py --json base.json --label base
#   ./startup_benchmark.py --compare base.json   # regression / improvement report

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

IMPORT_SNIPPET = "import avl"

AVL_IMPORT_SNIPPET = (
    "import time, cocotb\n"
    "t = time.perf_counter()\n"
    "import avl\n"
    "print(time.perf_counter() - t)\n"
)


class Result:
    """Timing samples for a single measurement, in seconds."""

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


def sh(cmd: list[str], cwd: Path, env: dict | None = None) -> float:
    """Run cmd, returning the elapsed wall time. Raises on failure."""
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return elapsed


def make_cmd(module: str, sim: str) -> list[str]:
    return ["make", "--no-print-directory", f"MODULE={module}", f"SIM={sim}"]


def clean_results(sim: str) -> None:
    """cocotb's makefile treats results.xml as the build target - it must not
    already exist or the run is skipped as up to date."""
    for stale in ("results.xml", "sim.log"):
        (HERE / stale).unlink(missing_ok=True)
    _ = sim


def time_import(iterations: int) -> Result:
    samples = []
    for _ in range(iterations):
        samples.append(sh([sys.executable, "-c", IMPORT_SNIPPET], cwd=HERE))
    return Result("import", "import avl (clean interpreter)", samples)


def time_avl_import(iterations: int) -> Result:
    """Time 'import avl' with cocotb already loaded.

    This is the shape a real simulation has - the simulator loads cocotb before
    it imports the testbench module - so it isolates AVL's own import cost from
    cocotb's. It is timed inside the child process, which makes it far less
    noisy than the surrounding process start-up."""
    samples = []
    for _ in range(iterations):
        proc = subprocess.run([sys.executable, "-c", AVL_IMPORT_SNIPPET],
                              cwd=HERE, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit("failed to time 'import avl'")
        samples.append(float(proc.stdout.strip()))
    return Result("avl_import", "import avl (cocotb preloaded)", samples)


def time_sim(module: str, sim: str, iterations: int, description: str) -> Result:
    samples = []
    for _ in range(iterations):
        clean_results(sim)
        samples.append(sh(make_cmd(module, sim), cwd=HERE))
    return Result(module, description, samples)


def build(sim: str) -> None:
    """Compile the DUT once so that compilation is not part of any sample."""
    clean_results(sim)
    sh(make_cmd("baseline", sim), cwd=HERE)


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000.0:8.1f}"


def report(results: dict[str, Result], iterations: int, sim: str, label: str | None) -> None:
    width = 78
    print()
    print("=" * width)
    title = "AVL start-up benchmark"
    if label:
        title += f" [{label}]"
    print(title)
    print("=" * width)
    print(f"simulator      : {sim}")
    print(f"iterations     : {iterations}")
    print(f"python         : {sys.version.split()[0]}")
    try:
        import avl

        print(f"avl version    : {getattr(avl, '__version__', 'unknown')}")
    except Exception:  # pragma: no cover - diagnostics only
        pass
    print("-" * width)
    print(f"{'measurement':<34}{'mean (ms)':>12}{'best (ms)':>12}{'stdev (ms)':>12}")
    print("-" * width)
    for r in results.values():
        print(f"{r.description:<34}{fmt_ms(r.mean):>12}{fmt_ms(r.best):>12}{fmt_ms(r.stdev):>12}")
    print("-" * width)

    overhead_mean = results["benchmark"].mean - results["baseline"].mean
    overhead_best = results["benchmark"].best - results["baseline"].best
    print(f"{'AVL start-up overhead':<34}{fmt_ms(overhead_mean):>12}{fmt_ms(overhead_best):>12}")
    pct = 100.0 * overhead_mean / results["baseline"].mean
    print(f"{'  as % of bare cocotb testbench':<34}{pct:>11.1f}%")
    if "avl_import" in results:
        imp = results["avl_import"].mean
        print(f"{'  of which import avl':<34}{fmt_ms(imp):>12}")
    if abs(overhead_mean) < 2.0 * results["benchmark"].stdev:
        print("  (overhead is within the noise of the full-simulation samples - "
              "raise -n\n   or compare 'import avl (cocotb preloaded)' instead)")
    print("=" * width)
    print()


def compare(results: dict[str, Result], previous: dict, iterations: int) -> None:
    width = 78
    prev_label = previous.get("label") or "previous"
    prev_results = previous["results"]
    print("=" * width)
    print(f"Comparison against '{prev_label}'")
    print("=" * width)
    print(f"{'measurement':<28}{prev_label[:10]:>11}{'now':>11}{'delta':>11}{'change':>11}")
    print("-" * width)
    for name, r in results.items():
        if name not in prev_results:
            continue
        old = prev_results[name]["mean"]
        new = r.mean
        delta = new - old
        pct = 100.0 * delta / old if old else 0.0
        print(f"{r.description[:27]:<28}{fmt_ms(old):>11}{fmt_ms(new):>11}"
              f"{fmt_ms(delta):>11}{pct:>10.1f}%")

    old_oh = prev_results["benchmark"]["mean"] - prev_results["baseline"]["mean"]
    new_oh = results["benchmark"].mean - results["baseline"].mean
    delta = new_oh - old_oh
    pct = 100.0 * delta / old_oh if old_oh else 0.0
    print("-" * width)
    print(f"{'AVL start-up overhead':<28}{fmt_ms(old_oh):>11}{fmt_ms(new_oh):>11}"
          f"{fmt_ms(delta):>11}{pct:>10.1f}%")
    print("=" * width)
    print()
    _ = iterations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure AVL testbench start-up time and the overhead over bare cocotb.")
    parser.add_argument("-n", "--iterations", type=int, default=3,
                        help="number of times to run each measurement (default: 3)")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--json", metavar="FILE",
                        help="write the raw results to FILE")
    parser.add_argument("--label", help="label recorded with --json and shown in reports")
    parser.add_argument("--compare", metavar="FILE",
                        help="compare these results against a previously saved --json file")
    parser.add_argument("--no-import", action="store_true",
                        help="skip the standalone 'import avl' measurement")
    args = parser.parse_args()

    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    print(f"building DUT for {args.sim} ...", flush=True)
    build(args.sim)

    results: dict[str, Result] = {}
    if not args.no_import:
        print(f"timing 'import avl' x{args.iterations} ...", flush=True)
        results["import"] = time_import(args.iterations)
        results["avl_import"] = time_avl_import(args.iterations)
    print(f"timing bare cocotb testbench x{args.iterations} ...", flush=True)
    results["baseline"] = time_sim("baseline", args.sim, args.iterations,
                                   "bare cocotb testbench")
    print(f"timing AVL testbench x{args.iterations} ...", flush=True)
    results["benchmark"] = time_sim("benchmark", args.sim, args.iterations,
                                  "AVL testbench (standard env)")

    report(results, args.iterations, args.sim, args.label)

    if args.json:
        payload = {
            "label": args.label,
            "iterations": args.iterations,
            "sim": args.sim,
            "python": sys.version.split()[0],
            "results": {name: r.as_dict() for name, r in results.items()},
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"results written to {args.json}")

    if args.compare:
        compare(results, json.loads(Path(args.compare).read_text()), args.iterations)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

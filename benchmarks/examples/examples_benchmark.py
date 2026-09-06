#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) examples benchmark.
#
# Measures the runtime of every example in examples/ twice - once against the
# working copy of AVL in this repository, and once against the released
# avl-core wheel of the same version number from PyPI - and reports the
# relative performance difference for each example.
#
# The two variants differ only in which AVL is imported:
#
#   local     - the AVL in this repository (the editable install in ./venv)
#   released  - avl-core==<version> installed from PyPI into its own virtual
#               environment. Shared dependencies (cocotb, z3-solver) are pinned
#               to the versions the local environment uses, so the simulator,
#               cocotb and the solver are identical in both variants.
#
# Each example is copied into a private work tree per variant, built once
# (warm-up runs are not timed, so Verilator compilation is never part of a
# sample), then run N times in each variant. Variants are interleaved so that
# machine drift affects both equally.
#
# Usage:
#   source ./avl.sh              # from the repository root
#   cd benchmarks/examples
#   ./examples_benchmark.py --dry-run          # show the plan, run nothing
#   ./examples_benchmark.py                    # 3 iterations, all examples
#   ./examples_benchmark.py -n 5 --only 'constraints/*'
#   ./examples_benchmark.py --json results/v1.0.1.json --markdown results/RESULTS.md

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
EXAMPLES_ROOT = REPO_ROOT / "examples"
AVL_SOURCE = REPO_ROOT / "avl"

# Copied work trees skip anything a previous run may have left behind.
COPY_IGNORE = shutil.ignore_patterns(
    "sim_build", "__pycache__", "*.pyc", "*.vcd", "*.fsdb", "results.xml",
    "sim.log", "html", ".passed", ".failed", "transcript", "modelsim.ini",
    "ucli.key",
)

# Files cocotb's makefile treats as build targets - a stale one skips the run.
STALE = ("results.xml", "sim.log")

# Packages installed into the released environment at the versions the local
# environment uses, so that AVL is the only thing that differs between the two
# variants. This covers avl-core's own dependencies and the packages the
# examples import but avl-core does not require - matplotlib ships only in this
# repository's [dev] extra, and an example importing it fails outright in an
# environment built from the released wheel alone.
DEFAULT_PINS = ("cocotb", "z3-solver", "pandas", "numpy", "matplotlib")


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


class Samples:
    """Timing samples for one example in one variant, in seconds."""

    def __init__(self, variant: str) -> None:
        self.variant = variant
        self.samples: list[float] = []
        self.status = "ok"
        self.detail = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok" and bool(self.samples)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples) if self.samples else float("nan")

    @property
    def best(self) -> float:
        return min(self.samples) if self.samples else float("nan")

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    def fail(self, status: str, detail: str) -> None:
        self.status = status
        self.detail = detail

    def as_dict(self) -> dict:
        return {
            "variant": self.variant,
            "status": self.status,
            "detail": self.detail,
            "samples": self.samples,
            "mean": self.mean,
            "best": self.best,
            "stdev": self.stdev,
        }


class ExampleResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.released = Samples("released")
        self.local = Samples("local")

    @property
    def comparable(self) -> bool:
        return self.released.ok and self.local.ok

    @property
    def delta(self) -> float:
        return self.local.mean - self.released.mean

    @property
    def change_pct(self) -> float:
        """Change in runtime. Negative means the local AVL is faster."""
        base = self.released.mean
        return 100.0 * self.delta / base if base else 0.0

    @property
    def speedup(self) -> float:
        """released / local. Greater than 1.0 means the local AVL is faster."""
        return self.released.mean / self.local.mean if self.local.mean else float("nan")

    @property
    def significant(self) -> bool:
        """True when the difference is larger than the run-to-run noise."""
        noise = max(self.released.stdev, self.local.stdev)
        return abs(self.delta) > 2.0 * noise

    def as_dict(self) -> dict:
        d = {
            "name": self.name,
            "released": self.released.as_dict(),
            "local": self.local.as_dict(),
        }
        if self.comparable:
            d.update({
                "delta": self.delta,
                "change_pct": self.change_pct,
                "speedup": self.speedup,
                "significant": self.significant,
            })
        return d


# ---------------------------------------------------------------------------
# discovery and versions
# ---------------------------------------------------------------------------


def local_version() -> str:
    """The version number of the AVL in this repository."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"could not read version from {REPO_ROOT / 'pyproject.toml'}")
    return match.group(1)


def discover_examples(only: list[str], skip: list[str]) -> list[tuple[str, Path]]:
    """Every runnable example, as (name relative to examples/, absolute path).

    Examples are identified the same way examples/Makefile identifies them: a
    directory holding a Makefile symlinked to the shared sim.mk."""
    found = []
    for makefile in sorted(EXAMPLES_ROOT.rglob("Makefile")):
        if not makefile.is_symlink():
            continue
        directory = makefile.parent
        found.append((str(directory.relative_to(EXAMPLES_ROOT)), directory))

    if only:
        found = [e for e in found if any(fnmatch.fnmatch(e[0], p) for p in only)]
    if skip:
        found = [e for e in found if not any(fnmatch.fnmatch(e[0], p) for p in skip)]
    return found


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout,
                          capture_output=True, text=True)


def check(cmd: list[str], what: str, cwd: Path | None = None,
          env: dict | None = None) -> str:
    proc = run(cmd, cwd=cwd, env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{what} failed: {' '.join(cmd)}")
    return proc.stdout


def pinned_versions(python: Path, packages: tuple[str, ...]) -> dict[str, str]:
    """The installed version of each package in the environment owning python."""
    snippet = (
        "import json, sys\n"
        "from importlib.metadata import version, PackageNotFoundError\n"
        "out = {}\n"
        "for name in sys.argv[1:]:\n"
        "    try:\n"
        "        out[name] = version(name)\n"
        "    except PackageNotFoundError:\n"
        "        pass\n"
        "print(json.dumps(out))\n"
    )
    proc = run([str(python), "-c", snippet, *packages])
    if proc.returncode != 0:
        return {}
    return json.loads(proc.stdout)


def released_versions_available(python: Path) -> list[str]:
    """Versions of avl-core on PyPI, or [] if pip could not tell us."""
    proc = run([str(python), "-m", "pip", "index", "versions", "avl-core",
                "--disable-pip-version-check"])
    if proc.returncode != 0:
        return []
    match = re.search(r"[Aa]vailable versions:\s*(.+)", proc.stdout)
    if not match:
        return []
    return [v.strip() for v in match.group(1).split(",")]


# ---------------------------------------------------------------------------
# environments
# ---------------------------------------------------------------------------


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / "python"


def venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def ensure_released_env(env_dir: Path, version: str, pins: dict[str, str],
                        rebuild: bool, verbose: bool) -> Path:
    """Create (or reuse) a virtual environment holding avl-core==version.

    The environment is stamped with what it was built from, so repeated runs
    reuse it and only rebuild when the version or the pins change."""
    stamp_file = env_dir / ".avl-benchmark-stamp"
    stamp = {"version": version, "pins": pins}

    if rebuild and env_dir.exists():
        print(f"removing {env_dir} ...", flush=True)
        shutil.rmtree(env_dir)

    if env_dir.exists():
        try:
            if json.loads(stamp_file.read_text()) == stamp:
                print(f"reusing released environment {env_dir}", flush=True)
                return env_dir
        except (OSError, ValueError):
            pass
        print(f"released environment is stale - rebuilding {env_dir} ...", flush=True)
        shutil.rmtree(env_dir)

    print(f"creating released environment {env_dir} ...", flush=True)
    check([sys.executable, "-m", "venv", str(env_dir)], "venv creation")

    python = venv_python(env_dir)
    quiet = [] if verbose else ["--quiet"]
    check([str(python), "-m", "pip", "install", "--upgrade", "pip", *quiet],
          "pip upgrade")

    requirements = [f"avl-core=={version}"]
    requirements += [f"{name}=={ver}" for name, ver in pins.items()]
    print(f"installing {' '.join(requirements)} ...", flush=True)
    proc = run([str(python), "-m", "pip", "install", *quiet, *requirements])
    if proc.returncode != 0 and pins:
        # The released avl-core may not accept the locally installed dependency
        # versions. Retry with the same packages unpinned - they still have to
        # be installed, since the examples import them - and say so, because the
        # comparison is then no longer dependency-for-dependency identical.
        sys.stderr.write(proc.stderr)
        print("WARNING: could not pin shared dependencies to the local versions;"
              " retrying with them unpinned", flush=True)
        stamp["pins"] = {}
        proc = run([str(python), "-m", "pip", "install", *quiet,
                    f"avl-core=={version}", *pins.keys()])
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        available = released_versions_available(python)
        if available:
            sys.stderr.write(f"\navl-core versions on PyPI: {', '.join(available)}\n")
        raise SystemExit(
            f"could not install avl-core=={version} from PyPI. Use "
            "--released-version to benchmark against a different release.")

    stamp_file.write_text(json.dumps(stamp, indent=2))
    return env_dir


def variant_env(venv: Path, sim: str, isolate_repo: bool, seed: int | None) -> dict:
    """The environment a variant's simulations run in.

    Everything is inherited except the parts that select the Python
    environment: PATH, VIRTUAL_ENV and PYTHONPATH. For the released variant,
    repository paths are stripped from PYTHONPATH so that the working copy of
    AVL cannot be picked up by accident."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)

    bin_dir = str(venv_bin(venv))
    known_bins = {str(venv_bin(Path(sys.prefix))), bin_dir}
    path = [p for p in env.get("PATH", "").split(os.pathsep) if p and p not in known_bins]
    env["PATH"] = os.pathsep.join([bin_dir, *path])
    env["VIRTUAL_ENV"] = str(venv)

    pythonpath = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    if isolate_repo:
        pythonpath = [p for p in pythonpath
                      if not str(Path(p).resolve()).startswith(str(REPO_ROOT))]
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    env["SIM"] = sim
    env.setdefault("TOPLEVEL_LANG", "verilog")
    env.setdefault("CXXFLAGS", "-std=c++17")

    # cocotb seeds Python's RNG from the wall clock unless told otherwise, so
    # without this every run randomizes differently: the two variants solve
    # different problems, which is noise in the thing being measured, and
    # examples whose outcome depends on the draw fail intermittently.
    if seed is not None:
        env["COCOTB_RANDOM_SEED"] = str(seed)
    return env


def describe_avl(venv: Path, env: dict) -> tuple[str, str]:
    """The version and file of the AVL an environment resolves to."""
    # Releases older than the working copy do not re-export __version__ at the
    # top level - it lives in avl._core - so try that before falling back to
    # the installed package metadata.
    snippet = (
        "import avl, avl._core\n"
        "from importlib.metadata import version, PackageNotFoundError\n"
        "v = getattr(avl, '__version__', None)\n"
        "if v is None:\n"
        "    v = getattr(avl._core, '__version__', None)\n"
        "if v is None:\n"
        "    try:\n"
        "        v = version('avl-core')\n"
        "    except PackageNotFoundError:\n"
        "        v = 'unknown'\n"
        "print(v)\n"
        "print(avl.__file__)\n"
    )
    proc = run([str(venv_python(venv)), "-c", snippet], env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"could not import avl from {venv}")
    version, location = proc.stdout.strip().splitlines()[:2]
    return version, location


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------


def prepare_worktree(work_root: Path, variant: str, reuse: bool) -> Path:
    """A private copy of examples/ for one variant.

    Each variant builds its own sim_build, so the two runs cannot invalidate
    each other's build, and neither writes into the repository's examples/."""
    destination = work_root / variant / "examples"
    if destination.exists():
        if reuse:
            return destination
        shutil.rmtree(work_root / variant)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXAMPLES_ROOT, destination, symlinks=True, ignore=COPY_IGNORE)
    return destination


def make_cmd(sim: str, no_trace: bool) -> list[str]:
    cmd = ["make", "--no-print-directory", "sim", f"SIM={sim}"]
    if no_trace:
        cmd.append("EXTRA_ARGS=")
    return cmd


def clean_stale(directory: Path) -> None:
    for name in STALE:
        (directory / name).unlink(missing_ok=True)


def passed(directory: Path) -> bool:
    """A run passed if it exited cleanly and reported no test failures.

    This is the same check examples/Makefile makes."""
    results = directory / "results.xml"
    if not results.exists():
        return False
    return "failure message=" not in results.read_text(errors="replace")


def run_once(directory: Path, env: dict, sim: str, no_trace: bool,
             timeout: int) -> tuple[float, bool, str]:
    """One timed `make sim`. Returns (elapsed, ok, detail)."""
    clean_stale(directory)
    start = time.perf_counter()
    try:
        proc = run(make_cmd(sim, no_trace), cwd=directory, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return time.perf_counter() - start, False, f"timed out after {timeout}s"
    elapsed = time.perf_counter() - start

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return elapsed, False, detail[-1] if detail else f"make exited {proc.returncode}"
    if not passed(directory):
        return elapsed, False, "test reported a failure"
    return elapsed, True, ""


def benchmark(examples: list[tuple[str, Path]], trees: dict[str, Path],
              envs: dict[str, dict], sim: str, iterations: int, warmup: int,
              no_trace: bool, timeout: int) -> list[ExampleResult]:
    results = []
    total = len(examples)

    for index, (name, _) in enumerate(examples, start=1):
        result = ExampleResult(name)
        print(f"[{index}/{total}] {name} ", end="", flush=True)

        # Warm-up: compiles the DUT in each work tree, so no timed sample
        # includes Verilator compilation. A variant that cannot even build is
        # not timed at all.
        broken = False
        for variant in ("released", "local"):
            directory = trees[variant] / name
            for _ in range(max(warmup, 1)):
                _, ok, detail = run_once(directory, envs[variant], sim, no_trace, timeout)
            if not ok:
                getattr(result, variant).fail("failed", detail)
                broken = True
        if broken:
            for variant in ("released", "local"):
                samples = getattr(result, variant)
                if samples.status == "ok":
                    samples.fail("skipped", "not timed - the other variant failed")
            print("- skipped (see report)", flush=True)
            results.append(result)
            continue

        for iteration in range(iterations):
            # Interleave the variants, alternating which goes first, so that
            # drift in machine load does not systematically favour either.
            order = ("released", "local") if iteration % 2 == 0 else ("local", "released")
            for variant in order:
                directory = trees[variant] / name
                elapsed, ok, detail = run_once(directory, envs[variant], sim,
                                               no_trace, timeout)
                samples = getattr(result, variant)
                if ok:
                    samples.samples.append(elapsed)
                else:
                    samples.fail("failed", detail)
            print(".", end="", flush=True)

        if result.comparable:
            print(f" {result.released.mean:6.2f}s -> {result.local.mean:6.2f}s "
                  f"({result.change_pct:+.1f}%)", flush=True)
        else:
            print(" incomplete", flush=True)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------


def geometric_mean(values: list[float]) -> float:
    if not values:
        return float("nan")
    return statistics.geometric_mean(values)


def report(results: list[ExampleResult], meta: dict) -> None:
    width = 96
    print()
    print("=" * width)
    title = "AVL examples benchmark - local working copy vs released avl-core"
    if meta.get("label"):
        title += f" [{meta['label']}]"
    print(title)
    print("=" * width)
    print(f"released       : avl-core {meta['released_version']} "
          f"({meta['released_location']})")
    print(f"local          : avl {meta['local_version']} ({meta['local_location']})")
    if meta["pins"]:
        print("pinned         : " + ", ".join(f"{k}=={v}" for k, v in meta["pins"].items()))
    else:
        print("pinned         : none - shared dependency versions may differ")
    print(f"simulator      : {meta['sim']}")
    print("random seed    : "
          + (str(meta["seed"]) if meta["seed"] is not None else "per-run, from the clock"))
    print(f"iterations     : {meta['iterations']} (plus {meta['warmup']} warm-up)")
    print(f"examples       : {len(results)}")
    print("-" * width)
    print(f"{'example':<44}{'released':>9}{'local':>10}{'delta':>10}"
          f"{'change':>11}{'speedup':>11}")
    print("-" * width)

    comparable = [r for r in results if r.comparable]
    for r in sorted(results, key=lambda r: r.change_pct if r.comparable else 1e9):
        if not r.comparable:
            continue
        flag = " " if r.significant else "~"
        print(f"{r.name[:43]:<43}{flag}{r.released.mean:9.3f}{r.local.mean:10.3f}"
              f"{r.delta:+10.3f}{r.change_pct:+10.1f}%{r.speedup:10.2f}x")

    print("-" * width)
    if comparable:
        released_total = sum(r.released.mean for r in comparable)
        local_total = sum(r.local.mean for r in comparable)
        overall = released_total / local_total if local_total else float("nan")
        geo = geometric_mean([r.speedup for r in comparable])
        change = 100.0 * (local_total - released_total) / released_total
        print(f"{'TOTAL (' + str(len(comparable)) + ' examples)':<44}"
              f"{released_total:9.3f}{local_total:10.3f}"
              f"{local_total - released_total:+10.3f}{change:+10.1f}%{overall:10.2f}x")
        print(f"{'geometric mean speedup':<44}{'':40}{geo:10.2f}x")
        faster = sum(1 for r in comparable if r.speedup > 1.0 and r.significant)
        slower = sum(1 for r in comparable if r.speedup < 1.0 and r.significant)
        noise = len(comparable) - faster - slower
        print(f"{'significantly faster / slower / in the noise':<44}"
              f"{faster:>17}{slower:>17}{noise:>17}")
        print("  '~' marks an example whose difference is inside its own run-to-run "
              "noise;\n  raise -n to resolve those.")

    skipped = [r for r in results if not r.comparable]
    if skipped:
        print("-" * width)
        print("not compared:")
        for r in skipped:
            for samples in (r.released, r.local):
                if samples.status != "ok":
                    print(f"  {r.name:<44}{samples.variant:<10}{samples.detail[:36]}")
    print("=" * width)
    print()


def markdown(results: list[ExampleResult], meta: dict, path: Path) -> None:
    comparable = [r for r in results if r.comparable]
    lines = [
        "# AVL examples benchmark",
        "",
        f"Local working copy of AVL {meta['local_version']} against the released "
        f"`avl-core=={meta['released_version']}` from PyPI.",
        "",
        f"- simulator: `{meta['sim']}`",
        f"- iterations: {meta['iterations']} (plus {meta['warmup']} warm-up)",
        f"- python: {meta['python']}",
        "- random seed: "
        + (f"`COCOTB_RANDOM_SEED={meta['seed']}`" if meta["seed"] is not None
           else "unpinned, drawn from the clock per run"),
        "- pinned shared dependencies: "
        + (", ".join(f"`{k}=={v}`" for k, v in meta["pins"].items()) or "none"),
        "",
        "Times are the mean wall time of a full `make sim`, in seconds. A negative",
        "change and a speedup above 1.00x mean the local AVL is faster.",
        "",
        "| example | released (s) | local (s) | change | speedup |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in sorted(comparable, key=lambda r: r.change_pct):
        note = "" if r.significant else " *"
        lines.append(f"| `{r.name}`{note} | {r.released.mean:.3f} | {r.local.mean:.3f} "
                     f"| {r.change_pct:+.1f}% | {r.speedup:.2f}x |")

    if comparable:
        released_total = sum(r.released.mean for r in comparable)
        local_total = sum(r.local.mean for r in comparable)
        overall = released_total / local_total
        change = 100.0 * (local_total - released_total) / released_total
        lines += [
            f"| **total ({len(comparable)} examples)** | **{released_total:.3f}** "
            f"| **{local_total:.3f}** | **{change:+.1f}%** | **{overall:.2f}x** |",
            "",
            f"Geometric mean speedup: **"
            f"{geometric_mean([r.speedup for r in comparable]):.2f}x**.",
            "",
            "`*` marks an example whose difference is within its own run-to-run noise.",
        ]

    skipped = [r for r in results if not r.comparable]
    if skipped:
        lines += ["", "## Not compared", "",
                  "| example | variant | reason |", "| --- | --- | --- |"]
        for r in skipped:
            for samples in (r.released, r.local):
                if samples.status != "ok":
                    lines.append(f"| `{r.name}` | {samples.variant} | {samples.detail} |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    print(f"markdown report written to {path}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the runtime of every example against the released "
                    "avl-core of the same version.")
    parser.add_argument("-n", "--iterations", type=int, default=3,
                        help="timed runs of each example in each variant (default: 3)")
    parser.add_argument("-w", "--warmup", type=int, default=1,
                        help="untimed runs before timing, which build the DUT "
                             "(default: 1)")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--released-version",
                        help="avl-core version to compare against "
                             "(default: the version in pyproject.toml)")
    parser.add_argument("--env-dir", type=Path,
                        help="virtual environment for the released avl-core "
                             "(default: benchmarks/examples/.venv-released-<version>)")
    parser.add_argument("--rebuild-env", action="store_true",
                        help="recreate the released environment from scratch")
    parser.add_argument("--pin", action="append", default=None, metavar="PKG",
                        help="pin PKG in the released environment to the locally "
                             f"installed version (default: {', '.join(DEFAULT_PINS)})")
    parser.add_argument("--no-pin", action="store_true",
                        help="let pip resolve the released environment's "
                             "dependencies freely")
    parser.add_argument("--work-dir", type=Path, default=HERE / "work",
                        help="where the per-variant copies of examples/ live "
                             "(default: benchmarks/examples/work)")
    parser.add_argument("--fresh-work", action="store_true",
                        help="re-copy the work trees instead of reusing them")
    parser.add_argument("--only", action="append", default=[], metavar="PATTERN",
                        help="only examples matching PATTERN, e.g. 'constraints/*' "
                             "(repeatable)")
    parser.add_argument("--skip", action="append", default=[], metavar="PATTERN",
                        help="skip examples matching PATTERN (repeatable)")
    parser.add_argument("--no-trace", action="store_true",
                        help="disable Verilator waveform tracing in both variants, "
                             "which removes VCD write time from every sample")
    parser.add_argument("--seed", type=int, default=1,
                        help="COCOTB_RANDOM_SEED for every run in both variants, so "
                             "they do identical work (default: 1)")
    parser.add_argument("--no-seed", action="store_true",
                        help="let cocotb seed from the clock, as a normal example run "
                             "does - runs then differ from each other")
    parser.add_argument("--timeout", type=int, default=600,
                        help="seconds allowed for a single example run (default: 600)")
    parser.add_argument("--json", metavar="FILE", help="write the raw results to FILE")
    parser.add_argument("--markdown", metavar="FILE",
                        help="write a markdown report to FILE")
    parser.add_argument("--label", help="label recorded with --json and shown in reports")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan - versions, environments and the "
                             "examples that would run - then exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show pip output when building the released environment")
    args = parser.parse_args()

    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if args.warmup < 1:
        parser.error("--warmup must be >= 1 - the first run compiles the DUT")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    seed = None if args.no_seed else args.seed
    version = args.released_version or local_version()
    env_dir = args.env_dir or (HERE / f".venv-released-{version}")
    pins = () if args.no_pin else tuple(args.pin or DEFAULT_PINS)
    pinned = pinned_versions(Path(sys.executable), pins) if pins else {}

    examples = discover_examples(args.only, args.skip)
    if not examples:
        parser.error("no examples matched")

    if args.dry_run:
        print(f"released version : avl-core=={version}")
        print(f"released env     : {env_dir}"
              f"{' (exists)' if env_dir.exists() else ' (would be created)'}")
        print("pins             : "
              + (", ".join(f"{k}=={v}" for k, v in pinned.items()) or "none"))
        print(f"local avl        : {REPO_ROOT}")
        print(f"work dir         : {args.work_dir}")
        print(f"simulator        : {args.sim}")
        print("random seed      : "
              + (str(seed) if seed is not None else "per-run, from the clock"))
        print(f"runs per example : {args.warmup} warm-up + {args.iterations} timed, "
              "per variant")
        print(f"examples         : {len(examples)}")
        for name, _ in examples:
            print(f"  {name}")
        return 0

    ensure_released_env(env_dir, version, pinned, args.rebuild_env, args.verbose)

    local_venv = Path(sys.prefix)
    envs = {
        "released": variant_env(env_dir, args.sim, isolate_repo=True, seed=seed),
        "local": variant_env(local_venv, args.sim, isolate_repo=False, seed=seed),
    }

    released_version, released_location = describe_avl(env_dir, envs["released"])
    installed_local_version, local_location = describe_avl(local_venv, envs["local"])

    # Guard against the two variants silently being the same AVL. What matters
    # is the working copy in AVL_SOURCE, not the repository as a whole - the
    # released environment lives inside the repository by default, and the
    # installed package inside it is a genuine PyPI build.
    released_path = Path(released_location).resolve()
    local_path = Path(local_location).resolve()
    if released_path.is_relative_to(AVL_SOURCE):
        raise SystemExit(
            f"the released environment resolves avl to {released_location}, which is "
            "the working copy - the two variants would be identical")
    if released_path == local_path:
        raise SystemExit(
            f"both variants resolve avl to {released_location} - they would be identical")
    if not local_path.is_relative_to(AVL_SOURCE):
        raise SystemExit(
            f"the local environment resolves avl to {local_location}, which is not the "
            f"working copy in {AVL_SOURCE} - source avl.sh from the repository root first")

    print(f"released : avl {released_version} ({released_location})")
    print(f"local    : avl {installed_local_version} ({local_location})")

    trees = {
        variant: prepare_worktree(args.work_dir, variant, reuse=not args.fresh_work)
        for variant in ("released", "local")
    }

    start = time.perf_counter()
    results = benchmark(examples, trees, envs, args.sim, args.iterations,
                        args.warmup, args.no_trace, args.timeout)
    elapsed = time.perf_counter() - start

    meta = {
        "label": args.label,
        "released_version": released_version,
        "released_location": released_location,
        "local_version": installed_local_version,
        "local_location": local_location,
        "pins": pinned,
        "sim": args.sim,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "no_trace": args.no_trace,
        "seed": seed,
        "python": sys.version.split()[0],
        "wall_time": elapsed,
    }

    report(results, meta)
    print(f"benchmark took {elapsed / 60.0:.1f} minutes")

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"meta": meta, "examples": [r.as_dict() for r in results]}, indent=2))
        print(f"results written to {path}")

    if args.markdown:
        markdown(results, meta, Path(args.markdown))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

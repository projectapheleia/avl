#!/usr/bin/env python3
# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) comparison benchmark.
#
# Measures what it costs to create, constrain and randomize an item, in four
# implementations of the same workload:
#
#   sv        SystemVerilog classes, solved and executed by the simulator
#   pyuvm     pyvsc randobjs, randomized from the run_phase of a pyuvm test,
#             out of a virtual environment this benchmark installs itself
#   released  the released avl-core from PyPI, in a virtual environment of its
#             own - reported under the version it is, avl-<version>
#   avl       the AVL in this repository - the editable install in ./venv
#
# The workload is the sixteen classes in rtl/classes.svh, cocotb/classes_avl.py
# and cocotb/classes_pyuvm.py: each declares the same representative set of
# variables - four unsigned logic vectors and two signed integers - under eleven
# constraints covering arithmetic, bitwise and related constructs, and they
# differ from one another in the constants those constraints are written with,
# so no implementation can amortize the analysis of one class across the rest.
# -N says how many of them take part.
#
# Every flavour compiles the same RTL, is built and run through cocotb's
# makefiles, drives the same clock and reset and does one item per rising edge.
# The only difference is who does that work.
#
# Each flavour is measured twice, driving the same number of clock cycles:
#
#   baseline  the work under test disabled - process startup, elaboration,
#             cocotb bringup, the class definitions and the loop itself
#   run       the work under test enabled
#
# The difference between the two is the cost of randomization. Baselines are not
# expected to agree between flavours - pyuvm pays for pyuvm's bringup, AVL for
# importing z3 - only to be the same for a flavour's own two phases, which is all
# the subtraction needs. Both are reported: the total run time is what a user
# waits for, the difference is what randomizing actually cost.
#
# Timing is process *tree* aware: Verilator solves SystemVerilog constraints in
# a separate z3 process which it never reaps, so getrusage() attributes none of
# that solver's CPU time to the simulator.
#
# Usage:
#   source ./avl.sh              # from the repository root
#   cd benchmarks/comparison
#   ./comparison_benchmark.py --dry-run        # show the plan, run nothing
#   ./comparison_benchmark.py                  # all 16 classes, 3 repeats
#   ./comparison_benchmark.py -N 1,4,16 -r 5
#   ./comparison_benchmark.py --flavours avl,released --output results/avl-only

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import resource
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
AVL_SOURCE = REPO_ROOT / "avl"

# Packages installed into the released environment at the versions the local
# environment uses, so that AVL is the only thing that differs between those two
# flavours. cocotb is pinned in the pyuvm environment for the same reason: the
# simulator interface has to be the same everywhere for the comparison to mean
# anything.
RELEASED_PINS = ("cocotb", "z3-solver")
PYUVM_PINS = ("cocotb",)

# What the pyuvm flavour needs, installed locally by this benchmark rather than
# alongside AVL - pyvsc is what does the randomizing, pyuvm hosts the loop.
PYUVM_REQUIREMENTS = ("pyuvm", "pyvsc")

FLAVOURS = ("sv", "pyuvm", "released", "avl")

# Items built per run, unless a run asks for a different number. One item of
# each class, and at least this many, because the randomization has to be
# comfortably larger than the run to run spread of the phases it is subtracted
# from - a couple of hundred milliseconds - for the difference to mean anything.
DEFAULT_ITEMS = 256

# The workload, in the three languages it is written in. All three hold the same
# classes, and a run checks that they still agree on how many.
SOURCES = {
    "sv": HERE / "rtl" / "classes.svh",
    "avl": HERE / "cocotb" / "classes_avl.py",
    "pyuvm": HERE / "cocotb" / "classes_pyuvm.py",
}

DESCRIPTIONS = {
    "sv": "SystemVerilog classes, randomized by the simulator",
    "pyuvm": "pyvsc randobjs, randomized from a pyuvm run_phase",
    "released": "released avl-core from PyPI",
    "avl": "the AVL in this repository",
}


# ---------------------------------------------------------------------------
# process tree aware timing
#
# Adapted from the timing harness of the randomization benchmark branch. Two
# independent measurements are taken and the larger of each is reported:
# getrusage(RUSAGE_CHILDREN), which is exact but only covers descendants that
# were waited for, and a sampler over every process in the run's process group,
# which covers everything but can miss the last few ticks of a process that dies
# between samples.
# ---------------------------------------------------------------------------

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
PAGE_SIZE_KB = os.sysconf("SC_PAGE_SIZE") // 1024

# getrusage reports the peak resident set in kilobytes on Linux and in bytes on
# macOS. Everything here is in kilobytes.
RUSAGE_RSS_DIVISOR = 1024 if sys.platform == "darwin" else 1


class TreeSampler(threading.Thread):
    """Sample the CPU time and RSS of every process in a process group.

    The per process counters are monotonic, so the highest value seen for a
    process is the best estimate of what it finished with, whether or not it was
    still alive at the final sample."""

    def __init__(self, pgid: int, interval: float = 0.02) -> None:
        super().__init__(daemon=True)
        self._pgid = pgid
        self._interval = interval
        self._done = threading.Event()
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
        return (sum(p[0] for p in self._peaks.values()),
                sum(p[1] for p in self._peaks.values()),
                sum(p[2] for p in self._peaks.values()))


class ProcSampler(TreeSampler):
    """Linux - every process is a directory under /proc."""

    # /proc/<pid>/stat fields, indexed from field 3 (state) - i.e. after the
    # "<pid> (<comm>)" prefix, which is skipped because comm may contain spaces.
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
                yield (int(entry.name),
                       int(fields[self.UTIME]) / CLOCK_TICKS,
                       int(fields[self.STIME]) / CLOCK_TICKS,
                       int(fields[self.RSS]) * PAGE_SIZE_KB)
            except (IndexError, ValueError):
                continue


class NullSampler(TreeSampler):
    """No /proc - getrusage has to stand on its own, and an unreaped solver
    process goes uncounted. Wall time is unaffected."""

    def snapshot(self) -> Iterable[tuple[int, float, float, int]]:
        return ()


def make_sampler(pgid: int, interval: float) -> TreeSampler:
    return ProcSampler(pgid, interval) if os.path.isdir("/proc") else NullSampler(pgid, interval)


def measure(cmd: list[str], cwd: Path, env: dict, log: Path | None,
            timeout: int, interval: float = 0.02) -> dict:
    """Run cmd once and return what it cost."""
    logfile = open(log, "wb") if log is not None else subprocess.DEVNULL
    timed_out = False

    try:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()

        try:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=logfile,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            return {"real_s": 0.0, "user_s": 0.0, "sys_s": 0.0, "cpu_pct": 0.0,
                    "max_rss_kb": 0, "status": f"error:{e.strerror}"}

        sampler = make_sampler(os.getpgid(proc.pid), interval)
        sampler.start()

        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            # The simulator is a grandchild of the make that was started, and
            # start_new_session made that make the leader of its own group, so
            # the group is what has to be killed.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                proc.kill()
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

    if timed_out:
        status = f"timeout:{timeout}s"
    elif returncode != 0:
        status = f"exit:{returncode}"
    else:
        status = "ok"

    return {"real_s": real, "user_s": user, "sys_s": system,
            "cpu_pct": 100.0 * (user + system) / real if real > 0 else 0.0,
            "max_rss_kb": int(rss), "status": status}


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


class Phase:
    """The repeats of one phase - baseline or run - of one flavour."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.samples: list[dict] = []

    def add(self, sample: dict) -> None:
        self.samples.append(sample)

    @property
    def ok(self) -> bool:
        return bool(self.samples) and all(s["status"] == "ok" for s in self.samples)

    def median(self, field: str) -> float:
        values = [s[field] for s in self.samples]
        return statistics.median(values) if values else float("nan")

    @property
    def cpu_s(self) -> float:
        return statistics.median(
            [s["user_s"] + s["sys_s"] for s in self.samples]) if self.samples else float("nan")

    @property
    def spread_pct(self) -> float:
        """Spread of the repeats, as a percentage of the median."""
        values = [s["real_s"] for s in self.samples]
        if len(values) < 2:
            return 0.0
        median = statistics.median(values)
        return 100.0 * (max(values) - min(values)) / median if median else 0.0

    def as_dict(self) -> dict:
        return {"phase": self.name, "samples": self.samples,
                "median_real_s": self.median("real_s"), "median_cpu_s": self.cpu_s}


class Result:
    """What one flavour cost, for one class count."""

    def __init__(self, flavour: str, classes: int, iterations: int) -> None:
        self.flavour = flavour
        self.classes = classes
        self.iterations = iterations
        self.baseline = Phase("baseline")
        self.run = Phase("run")
        self.status = "ok"
        self.detail = ""

    def fail(self, status: str, detail: str) -> None:
        self.status = status
        self.detail = detail

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.baseline.ok and self.run.ok

    @property
    def total_s(self) -> float:
        """Wall time of the whole run - what a user waits for."""
        return self.run.median("real_s")

    @property
    def work_s(self) -> float:
        """Wall time the randomization cost, with everything else subtracted."""
        return self.run.median("real_s") - self.baseline.median("real_s")

    @property
    def cpu_work_s(self) -> float:
        return self.run.cpu_s - self.baseline.cpu_s

    @property
    def per_item_us(self) -> float:
        return 1e6 * self.work_s / self.iterations if self.iterations else float("nan")

    @property
    def cpu_per_item_us(self) -> float:
        return 1e6 * self.cpu_work_s / self.iterations if self.iterations else float("nan")

    def as_dict(self) -> dict:
        d = {"flavour": self.flavour, "classes": self.classes,
             "iterations": self.iterations, "status": self.status, "detail": self.detail,
             "baseline": self.baseline.as_dict(), "run": self.run.as_dict()}
        if self.ok:
            d.update({"total_s": self.total_s, "work_s": self.work_s,
                      "cpu_work_s": self.cpu_work_s,
                      "per_item_us": self.per_item_us,
                      "cpu_per_item_us": self.cpu_per_item_us,
                      "max_rss_kb": max(s["max_rss_kb"] for s in self.run.samples)})
        return d


# ---------------------------------------------------------------------------
# environments
# ---------------------------------------------------------------------------


def workload_classes() -> int:
    """How many classes the three renderings of the workload hold.

    They are three files that have to say the same thing, so a run checks that
    they still do rather than silently comparing different workloads."""
    counts = {flavour: len(re.findall(r"^class item_\d+", path.read_text(), re.MULTILINE))
              for flavour, path in SOURCES.items()}

    if len(set(counts.values())) != 1:
        raise SystemExit("the three renderings of the workload disagree on how many "
                         "classes there are: "
                         + ", ".join(f"{k} has {v}" for k, v in counts.items()))

    total = next(iter(counts.values()))
    if not total:
        raise SystemExit(f"no classes found in {SOURCES['avl']}")
    return total


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
            timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout,
                          capture_output=True, text=True)


def check(cmd: list[str], what: str, cwd: Path | None = None,
          env: dict | None = None) -> str:
    proc = run_cmd(cmd, cwd=cwd, env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{what} failed: {' '.join(cmd)}")
    return proc.stdout


def venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def venv_python(venv: Path) -> Path:
    return venv_bin(venv) / "python"


def local_version() -> str:
    """The version number of the AVL in this repository."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"could not read version from {REPO_ROOT / 'pyproject.toml'}")
    return match.group(1)


def released_versions(python: Path) -> list[str]:
    """Versions of avl-core on PyPI, newest first, or [] if pip could not tell us."""
    proc = run_cmd([str(python), "-m", "pip", "index", "versions", "avl-core",
                    "--disable-pip-version-check"])
    if proc.returncode != 0:
        return []
    match = re.search(r"[Aa]vailable versions:\s*(.+)", proc.stdout)
    return [v.strip() for v in match.group(1).split(",")] if match else []


def latest_released() -> str:
    """The newest avl-core on PyPI, falling back to this repository's version."""
    versions = released_versions(Path(sys.executable))
    if versions:
        return versions[0]
    print("WARNING: could not ask PyPI what the latest avl-core is - falling back to "
          "the version in pyproject.toml", flush=True)
    return local_version()


def pinned_versions(python: Path, packages: Iterable[str]) -> dict[str, str]:
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
    proc = run_cmd([str(python), "-c", snippet, *packages])
    return json.loads(proc.stdout) if proc.returncode == 0 else {}


def ensure_env(env_dir: Path, requirements: list[str], rebuild: bool,
               verbose: bool, what: str) -> Path:
    """Create - or reuse - a virtual environment holding exactly requirements.

    The environment is stamped with what it was built from, so repeated runs
    reuse it and it is only rebuilt when the requirements change."""
    stamp_file = env_dir / ".avl-benchmark-stamp"
    stamp = {"requirements": sorted(requirements)}

    if rebuild and env_dir.exists():
        print(f"removing {env_dir} ...", flush=True)
        shutil.rmtree(env_dir)

    if env_dir.exists():
        try:
            if json.loads(stamp_file.read_text()) == stamp:
                print(f"reusing {what} environment {env_dir.name}", flush=True)
                return env_dir
        except (OSError, ValueError):
            pass
        print(f"{what} environment is stale - rebuilding {env_dir.name} ...", flush=True)
        shutil.rmtree(env_dir)

    print(f"creating {what} environment {env_dir.name} ...", flush=True)
    check([sys.executable, "-m", "venv", str(env_dir)], "venv creation")

    python = venv_python(env_dir)
    quiet = [] if verbose else ["--quiet"]
    check([str(python), "-m", "pip", "install", "--upgrade", "pip", *quiet], "pip upgrade")

    print(f"installing {' '.join(requirements)} ...", flush=True)
    proc = run_cmd([str(python), "-m", "pip", "install", *quiet, *requirements])
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"could not build the {what} environment in {env_dir}")

    stamp_file.write_text(json.dumps(stamp, indent=2))
    return env_dir


def flavour_env(venv: Path, sim: str, isolate_repo: bool, seed: int) -> dict:
    """The environment one flavour's simulations run in.

    Everything is inherited except the parts that select the Python environment:
    PATH, VIRTUAL_ENV and PYTHONPATH. For every flavour but the local one,
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

    # cocotb seeds Python's random module from this, and the simulator's own
    # solver is seeded with it through sim.mk. Without it every run solves a
    # different problem, which is noise in the thing being measured.
    env["COCOTB_RANDOM_SEED"] = str(seed)

    # pyvsc is noisy with deprecation warnings on Python 3.12, and cocotb logs
    # every one of them. Silenced for every flavour alike, so that what is
    # measured is the randomization rather than the warning machinery.
    env["PYTHONWARNINGS"] = "ignore::DeprecationWarning"

    return env


def describe_avl(venv: Path, env: dict) -> tuple[str, str]:
    """The version and file of the AVL an environment resolves to."""
    # Releases older than the working copy do not re-export __version__ at the
    # top level - it lives in avl._core - so try that before falling back to the
    # installed package metadata.
    snippet = (
        "import avl, avl._core\n"
        "from importlib.metadata import version, PackageNotFoundError\n"
        "v = getattr(avl, '__version__', None) or getattr(avl._core, '__version__', None)\n"
        "if v is None:\n"
        "    try:\n"
        "        v = version('avl-core')\n"
        "    except PackageNotFoundError:\n"
        "        v = 'unknown'\n"
        "print(v)\n"
        "print(avl.__file__)\n"
    )
    # Run from outside the repository: an interpreter started in the repository
    # root would find the working copy of avl/ on sys.path whatever environment
    # it belongs to.
    proc = run_cmd([str(venv_python(venv)), "-c", snippet], cwd=venv, env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"could not import avl from {venv}")
    version, location = proc.stdout.strip().splitlines()[:2]
    return version, location


# ---------------------------------------------------------------------------
# what it was measured on
#
# A time means little without the machine that produced it and the versions of
# the tools that spent it, so every report carries both. Everything here
# degrades to "unknown" rather than failing.
# ---------------------------------------------------------------------------

VERSION_COMMANDS = {
    "verilator": ["verilator", "--version"],
    "questa": ["vsim", "-version"],
    "modelsim": ["vsim", "-version"],
    "vcs": ["vcs", "-ID"],
    "xcelium": ["xrun", "-version"],
    "icarus": ["iverilog", "-V"],
}

# Fields /proc/cpuinfo may name the processor in, in the order they are tried.
CPU_MODEL_KEYS = ("model name", "cpu model", "hardware", "machine", "cpu")


def first_line(text: str | None) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return " ".join(line.split())
    return ""


def tool_version(tool: str, env: dict) -> str:
    """Version of one simulator, as it reports itself."""
    cmd = VERSION_COMMANDS.get(tool)
    if cmd is None:
        return "unknown"
    try:
        done = run_cmd(cmd, env=env, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return f"{tool} (not on PATH)"
    return first_line(done.stdout) or first_line(done.stderr) or f"{tool} (not on PATH)"


def machine() -> dict:
    """The processor, the cores, the memory and the operating system."""
    info = {"os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(), "cpu": "unknown",
            "cores": None, "threads": os.cpu_count(), "memory_gb": None}

    try:
        blocks = []
        for chunk in Path("/proc/cpuinfo").read_text().split("\n\n"):
            fields = {}
            for line in chunk.splitlines():
                key, sep, value = line.partition(":")
                if sep and value.strip():
                    fields[key.strip().lower()] = value.strip()
            if fields:
                blocks.append(fields)
        if blocks:
            info["cpu"] = next((blocks[0][k] for k in CPU_MODEL_KEYS if k in blocks[0]),
                               "unknown")
            # A physical core is a (socket, core) pair; hyperthreads share one.
            cores = {(b.get("physical id"), b.get("core id")) for b in blocks if "core id" in b}
            info["cores"] = len(cores) or None
            info["threads"] = len(blocks)
    except OSError:
        pass

    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["memory_gb"] = round(int(line.split()[1]) / 1024 / 1024, 1)
                break
    except (OSError, IndexError, ValueError):
        pass

    return info


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------


def make_cmd(rundir: Path, flavour: str, sim: str, seed: int, classes: int,
             work: bool, burst: int) -> list[str]:
    return ["make", "--no-print-directory", "-C", str(rundir),
            "-f", str(HERE / "sim.mk"), "sim",
            f"FLAVOUR={flavour}", f"SIM={sim}", f"SEED={seed}",
            f"RUN_PLUSARGS=+work={int(work)} +burst={burst} +classes={classes}"]


def phase_env(base: dict, classes: int, iterations: int, burst: int, work: bool) -> dict:
    env = dict(base)
    env["BENCH_CLASSES"] = str(classes)
    env["BENCH_ITERATIONS"] = str(iterations)
    env["BENCH_BURST"] = str(burst)
    env["BENCH_WORK"] = "1" if work else "0"
    # cocotb's makefiles are invoked from a make with no jobserver to pass on.
    env["MAKEFLAGS"] = ""
    return env


def passed(rundir: Path) -> bool:
    """A run passed if cocotb reported no test failures - the check the examples
    make as well."""
    results = rundir / "results.xml"
    if not results.exists():
        return False
    return "failure message=" not in results.read_text(errors="replace")


def one_run(rundir: Path, cmd: list[str], env: dict, log: Path, timeout: int) -> dict:
    sample = measure(cmd, rundir, env, log, timeout)
    if sample["status"] == "ok" and not passed(rundir):
        sample["status"] = "failed"
    return sample


def failure_detail(log: Path) -> str:
    """The last thing a failed run said, for the report."""
    try:
        lines = [ln.strip() for ln in log.read_text(errors="replace").splitlines() if ln.strip()]
    except OSError:
        return "no log"
    return lines[-1][:120] if lines else "no output"


def measure_flavour(flavour: str, classes: int, iterations: int, burst: int,
                    rundir: Path, base_env: dict, sim: str, seed: int,
                    repeats: int, warmup: int, timeout: int) -> Result:
    """Build, warm and then measure both phases of one flavour."""
    result = Result(flavour, classes, iterations)
    rundir.mkdir(parents=True, exist_ok=True)

    baseline_cmd = make_cmd(rundir, flavour, sim, seed, classes, work=False, burst=burst)
    work_cmd = make_cmd(rundir, flavour, sim, seed, classes, work=True, burst=burst)
    baseline_env = phase_env(base_env, classes, iterations, burst, work=False)
    work_env = phase_env(base_env, classes, iterations, burst, work=True)

    # Compiling the model is not part of any measurement, so it happens here,
    # once, with the work disabled.
    print(f"  {flavour:9s} building ", end="", flush=True)
    sample = one_run(rundir, baseline_cmd, baseline_env, rundir / "build.log", timeout)
    if sample["status"] != "ok":
        result.fail("failed", f"build: {failure_detail(rundir / 'build.log')}")
        print(f"FAILED - see {rundir / 'build.log'}", flush=True)
        return result

    # Untimed runs first, so that no measured run is the one paying for a cold
    # file cache or for writing .pyc files.
    for _ in range(warmup):
        sample = one_run(rundir, work_cmd, work_env, rundir / "warm.log", timeout)
        if sample["status"] != "ok":
            result.fail("failed", f"warm-up: {failure_detail(rundir / 'warm.log')}")
            print(f"FAILED - see {rundir / 'warm.log'}", flush=True)
            return result

    # The two phases are interleaved rather than run in blocks, so that drift in
    # machine load moves both of them together.
    for _repeat in range(repeats):
        for phase, cmd, env, log in (
                (result.baseline, baseline_cmd, baseline_env, rundir / "baseline.log"),
                (result.run, work_cmd, work_env, rundir / "run.log")):
            sample = one_run(rundir, cmd, env, log, timeout)
            sample["repeat"] = _repeat
            phase.add(sample)
            if sample["status"] != "ok":
                result.fail("failed", f"{phase.name}: {failure_detail(log)}")
                print(f"FAILED - see {log}", flush=True)
                return result
        print(".", end="", flush=True)

    print(f" {result.per_item_us:9.1f} us/item"
          f"  (run {result.run.median('real_s'):.2f}s - baseline "
          f"{result.baseline.median('real_s'):.2f}s)", flush=True)
    return result


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------


def by_classes(results: list[Result]) -> list[tuple[int, list[Result]]]:
    counts = sorted({r.classes for r in results})
    return [(n, [r for r in results if r.classes == n]) for n in counts]


def fastest(group: list[Result], field: str = "per_item_us") -> float:
    usable = [getattr(r, field) for r in group if r.ok and getattr(r, field) > 0]
    return min(usable) if usable else float("nan")


def head_to_head(group: list[Result]) -> list[tuple[str, float, float]]:
    """The local AVL against each of the others, as (other, randomization, total).

    Both figures are ratios: how many times the other flavour's cost is the
    local one's."""
    ok = {r.flavour: r for r in group if r.ok}
    local = ok.get("avl")
    if local is None or local.per_item_us <= 0:
        return []

    out = []
    for other in ("released", "pyuvm", "sv"):
        result = ok.get(other)
        if result is not None and result.per_item_us > 0:
            out.append((other,
                        result.per_item_us / local.per_item_us,
                        result.total_s / local.total_s if local.total_s else float("nan")))
    return out


def faster_by(ratio: float) -> tuple[float, str]:
    """How much faster - or, below 1.0, how much slower - as a figure and a word."""
    if ratio >= 1.0:
        return ratio, "faster"
    return (1.0 / ratio if ratio else float("inf")), "slower"


def machine_line(meta: dict) -> str:
    m = meta["machine"]
    cores = f"{m['cores']} cores" if m["cores"] else f"{m['threads']} cpus"
    threads = f" / {m['threads']} threads" if m["cores"] else ""
    memory = f", {m['memory_gb']} GB" if m["memory_gb"] else ""
    return f"{m['cpu']}, {cores}{threads}{memory}"


def name_of(meta: dict, flavour: str) -> str:
    """What a flavour is called in the report - the released AVL by its version."""
    return meta["names"].get(flavour, flavour)


def rss_mb(result: Result) -> float:
    return max(s["max_rss_kb"] for s in result.run.samples) / 1024.0


def report(results: list[Result], meta: dict) -> None:
    width = 92
    print()
    print("=" * width)
    title = "AVL comparison benchmark - creating, constraining and randomizing an item"
    if meta.get("label"):
        title += f" [{meta['label']}]"
    print(title)
    print("=" * width)
    print(f"machine     : {machine_line(meta)}")
    print(f"os          : {meta['machine']['os']} ({meta['machine']['arch']})")
    print(f"simulator   : {meta['simulator']}")
    print(f"python      : {meta['python']}")
    for flavour in meta["flavours"]:
        print(f"{name_of(meta, flavour):12s}: {meta['versions'][flavour]}")
    print(f"seed        : {meta['seed']}")
    print(f"repeats     : {meta['repeats']} (plus {meta['warmup']} warm-up), "
          f"median reported")

    for classes, group in by_classes(results):
        items = group[0].iterations
        print("-" * width)
        print(f"{classes} classes, {items} items - {items / classes:.3g} of each class, "
              "in turn")

        # Total run time - what a user waits for, start-up and all.
        best_total = fastest(group, "total_s")
        print()
        print("total run time - the whole simulation, start to finish")
        print(f"{'flavour':<14}{'run':>10}{'relative':>11}{'cpu':>8}{'peak rss':>11}")
        for result in sorted(group, key=lambda r: r.total_s if r.ok else 1e18):
            if not result.ok:
                print(f"{name_of(meta, result.flavour):<14}{'not measured - see below':>40}")
                continue
            print(f"{name_of(meta, result.flavour):<14}"
                  f"{result.total_s:9.2f}s"
                  f"{result.total_s / best_total:10.2f}x"
                  f"{result.run.median('cpu_pct'):7.0f}%"
                  f"{rss_mb(result):8.0f} MB")

        # Randomization - the same runs with the baseline taken off them.
        best = fastest(group)
        print()
        print("randomization - the same runs with the work disabled subtracted from them")
        print(f"{'flavour':<14}{'baseline':>10}{'randomizing':>13}"
              f"{'us/item':>11}{'cpu us/item':>13}{'relative':>10}")
        for result in sorted(group, key=lambda r: r.per_item_us if r.ok else 1e18):
            if not result.ok:
                print(f"{name_of(meta, result.flavour):<14}{'not measured - see below':>40}")
                continue
            print(f"{name_of(meta, result.flavour):<14}"
                  f"{result.baseline.median('real_s'):9.2f}s"
                  f"{result.work_s:12.2f}s"
                  f"{result.per_item_us:11.1f}"
                  f"{result.cpu_per_item_us:13.1f}"
                  f"{result.per_item_us / best:9.2f}x")

        lost = [name_of(meta, r.flavour) for r in group if r.ok and r.work_s <= 0]
        if lost:
            print(f"  {', '.join(lost)}: the randomization did not rise above the "
                  "run-to-run spread - raise -n or -r")

        pairs = head_to_head(group)
        if pairs:
            print()
            for other, rand, total in pairs:
                rand_figure, rand_word = faster_by(rand)
                total_figure, total_word = faster_by(total)
                print(f"  avl against {name_of(meta, other):<12}: "
                      f"{rand_figure:5.2f}x {rand_word} at randomizing, "
                      f"{total_figure:5.2f}x {total_word} over the whole run")

    failed = [r for r in results if not r.ok]
    if failed:
        print("-" * width)
        print("not measured:")
        for result in failed:
            print(f"  {name_of(meta, result.flavour):<12} {result.classes:>3} classes  "
                  f"{result.detail}")

    print("-" * width)
    print("Times are wall clock seconds, medians of the repeats. The total run time is")
    print("the whole simulation - process startup, elaboration, cocotb bringup, the")
    print("class definitions, the loop and the randomization. Subtracting a run with")
    print("the randomization disabled from it leaves the randomization on its own,")
    print("which is what 'us/item' divides by the items. 'cpu us/item' is the same")
    print("subtraction over user+system time across the whole process tree, which is")
    print("where a simulator's external SMT solver shows up.")
    print("=" * width)
    print()


def markdown(results: list[Result], meta: dict, path: Path) -> None:
    lines = [
        "# AVL comparison benchmark",
        "",
        "What it costs to create, constrain and randomize one item, in four",
        "implementations of the same workload - sixteen classes, each declaring four",
        "unsigned logic vectors and two signed integers under eleven arithmetic,",
        "bitwise and related constraints, and each written with different constants.",
        "",
        "| | |",
        "| --- | --- |",
        *([f"| label | {meta['label']} |"] if meta.get("label") else []),
        f"| machine | {machine_line(meta)} |",
        f"| os | {meta['machine']['os']} ({meta['machine']['arch']}) |",
        f"| simulator | {meta['simulator']} |",
        f"| python | {meta['python']} |",
    ]
    lines += [f"| {name_of(meta, flavour)} | {meta['versions'][flavour]} |"
              for flavour in meta["flavours"]]
    lines += [
        f"| seed | {meta['seed']} |",
        f"| repeats | {meta['repeats']} (plus {meta['warmup']} warm-up), median reported |",
        "",
    ]

    for classes, group in by_classes(results):
        items = group[0].iterations
        lines += [f"## {classes} classes, {items} items", ""]

        best_total = fastest(group, "total_s")
        lines += [
            "### Total run time",
            "",
            "The whole simulation, start to finish.",
            "",
            "| flavour | what it is | run (s) | relative | cpu | peak rss (MB) |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for result in sorted(group, key=lambda r: r.total_s if r.ok else 1e18):
            name = f"`{name_of(meta, result.flavour)}`"
            what = DESCRIPTIONS[result.flavour]
            if not result.ok:
                lines.append(f"| {name} | {what} | - | - | - | not measured |")
                continue
            lines.append(f"| {name} | {what} | **{result.total_s:.2f}** "
                         f"| {result.total_s / best_total:.2f}x "
                         f"| {result.run.median('cpu_pct'):.0f}% "
                         f"| {rss_mb(result):.0f} |")

        best = fastest(group)
        lines += [
            "",
            "### Randomization",
            "",
            "The same runs with the work disabled subtracted from them.",
            "",
            "| flavour | baseline (s) | randomizing (s) | us/item | cpu us/item "
            "| relative |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for result in sorted(group, key=lambda r: r.per_item_us if r.ok else 1e18):
            name = f"`{name_of(meta, result.flavour)}`"
            if not result.ok:
                lines.append(f"| {name} | - | - | - | - | not measured |")
                continue
            lines.append(f"| {name} | {result.baseline.median('real_s'):.2f} "
                         f"| {result.work_s:.2f} | **{result.per_item_us:.1f}** "
                         f"| {result.cpu_per_item_us:.1f} "
                         f"| {result.per_item_us / best:.2f}x |")

        pairs = head_to_head(group)
        if pairs:
            lines += ["", "The AVL in this repository against each of the others:", "",
                      "| against | randomizing | whole run |", "| --- | ---: | ---: |"]
            for other, rand, total in pairs:
                rand_figure, rand_word = faster_by(rand)
                total_figure, total_word = faster_by(total)
                lines.append(f"| `{name_of(meta, other)}` "
                             f"| **{rand_figure:.2f}x** {rand_word} "
                             f"| **{total_figure:.2f}x** {total_word} |")
        lines.append("")

    failed = [r for r in results if not r.ok]
    if failed:
        lines += ["## Not measured", "", "| flavour | classes | reason |",
                  "| --- | ---: | --- |"]
        lines += [f"| `{name_of(meta, r.flavour)}` | {r.classes} | {r.detail} |"
                  for r in failed]
        lines.append("")

    lines += [
        "## How to read it",
        "",
        "Times are wall clock seconds, medians of the repeats. The total run time is",
        "the whole simulation - process startup, elaboration, cocotb bringup, the class",
        "definitions, the loop and the randomization - which is what a user waits for,",
        "and why a flavour can win on randomization and lose on the run.",
        "",
        "Each flavour is also run over the same number of clock cycles with the",
        "randomization disabled, and subtracting that leaves the randomization on its",
        "own. Baselines are not expected to agree between flavours, only to be the same",
        "for a flavour's own two phases.",
        "",
        "`cpu us/item` is the same subtraction over user + system time across the whole",
        "process tree. A SystemVerilog simulator solves constraints in a separate SMT",
        "solver process which it never reaps, so that time is invisible to `getrusage()`",
        "and appears only here.",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_csv(results: list[Result], path: Path) -> None:
    """Every timed run, one row each - the raw material of the report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["classes", "iterations", "flavour", "phase", "repeat", "real_s",
              "user_s", "sys_s", "cpu_pct", "max_rss_kb", "status"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for phase in (result.baseline, result.run):
                for sample in phase.samples:
                    writer.writerow({
                        "classes": result.classes, "iterations": result.iterations,
                        "flavour": result.flavour, "phase": phase.name,
                        "repeat": sample.get("repeat", 0),
                        "real_s": round(sample["real_s"], 4),
                        "user_s": round(sample["user_s"], 4),
                        "sys_s": round(sample["sys_s"], 4),
                        "cpu_pct": round(sample["cpu_pct"], 1),
                        "max_rss_kb": sample["max_rss_kb"], "status": sample["status"]})


# ---------------------------------------------------------------------------
# HTML report
#
# Self contained - no scripts, no fonts, nothing fetched - so results/ can be
# copied or published as it stands.
# ---------------------------------------------------------------------------

COLOURS = {"sv": "#8C3B52", "pyuvm": "#B4762A", "released": "#5C6B66", "avl": "#1F6F5C"}

CSS = """
:root { color-scheme: light; }
body { margin: 0; padding: 2.5rem 1.5rem; background: #F7F9F8; color: #131A18;
       font: 15px/1.55 "DejaVu Sans", "Helvetica Neue", Arial, sans-serif; }
main { max-width: 62rem; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 .3rem; }
h2 { font-size: 1.15rem; margin: 2.2rem 0 .6rem; }
h3 { font-size: 1rem; margin: 0 0 .2rem; }
p.note { margin: 0 0 .8rem; }
p.lead { color: #5C6B66; margin: 0 0 1.8rem; max-width: 46rem; }
section { background: #FFF; border: 1px solid #D8E0DD; border-radius: 6px;
          padding: 1.1rem 1.3rem; margin-bottom: 1.2rem; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { padding: .38rem .55rem; border-bottom: 1px solid #EDF1F0; text-align: right; }
th:first-child, td:first-child, th.left, td.left { text-align: left; }
thead th { border-bottom: 1px solid #D8E0DD; color: #5C6B66; font-weight: 600; }
tbody tr:last-child td { border-bottom: none; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: .88em; }
.env { display: grid; grid-template-columns: 11rem 1fr; gap: .3rem 1rem; font-size: .9rem; }
.env dt { color: #5C6B66; }
.env dd { margin: 0; }
.h2h { display: flex; flex-wrap: wrap; gap: .8rem; margin-top: .9rem; }
.h2h div { flex: 1 1 12rem; border: 1px solid #D8E0DD; border-radius: 5px;
           padding: .6rem .8rem; }
.h2h b { font-size: 1.35rem; display: block; color: #1F6F5C; }
.h2h b.slower { color: #8C3B52; }
.h2h span { color: #5C6B66; font-size: .85rem; }
.chart { margin-top: 1rem; overflow-x: auto; }
.note { color: #5C6B66; font-size: .88rem; }
.fail { color: #8C3B52; }
footer { color: #5C6B66; font-size: .85rem; margin-top: 2rem; }
"""


def esc(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def svg_bars(group: list[Result], meta: dict, field: str, unit: str,
             what: str) -> str:
    """One horizontal bar per flavour, over one of the two figures."""
    rows = [r for r in sorted(group, key=lambda r: getattr(r, field) if r.ok else 1e18)
            if r.ok]
    if not rows:
        return ""

    width, row_h, pad_l, pad_r, pad_t = 720, 34, 110, 100, 10
    height = pad_t * 2 + row_h * len(rows)
    top = max(getattr(r, field) for r in rows) or 1.0
    span = width - pad_l - pad_r

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'role="img" aria-label="{esc(what)} by flavour">']
    for index, result in enumerate(rows):
        y = pad_t + index * row_h
        value = getattr(result, field)
        bar = max(span * value / top, 1.0)
        colour = COLOURS.get(result.flavour, "#5C6B66")
        label = f"{value:,.0f} {unit}" if value >= 10 else f"{value:,.2f} {unit}"
        out.append(f'<text x="{pad_l - 10}" y="{y + 18}" text-anchor="end" '
                   f'font-size="13" fill="#131A18">'
                   f'{esc(name_of(meta, result.flavour))}</text>')
        out.append(f'<rect x="{pad_l}" y="{y + 5}" width="{bar:.1f}" height="18" '
                   f'rx="2" fill="{colour}"/>')
        out.append(f'<text x="{pad_l + bar + 8:.1f}" y="{y + 18}" font-size="12" '
                   f'fill="{colour}">{label}</text>')
    out.append("</svg>")
    return "".join(out)


def html_report(results: list[Result], meta: dict, path: Path) -> None:
    m = meta["machine"]
    env_rows = [
        *([("label", meta["label"])] if meta.get("label") else []),
        ("machine", machine_line(meta)),
        ("os", f"{m['os']} ({m['arch']})"),
        ("simulator", meta["simulator"]),
        ("python", meta["python"]),
        *[(name_of(meta, flavour), meta["versions"][flavour])
          for flavour in meta["flavours"]],
        ("seed", str(meta["seed"])),
        ("repeats", f"{meta['repeats']} (plus {meta['warmup']} warm-up), median reported"),
        ("measured", meta["date"]),
    ]

    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        f"<title>AVL comparison benchmark{' - ' + esc(meta['label']) if meta.get('label') else ''}"
        "</title>",
        f"<style>{CSS}</style></head><body><main>",
        "<h1>AVL comparison benchmark</h1>",
        "<p class=\"lead\">What it costs to create, constrain and randomize one item, in "
        "four implementations of the same workload: sixteen classes, each declaring four "
        "unsigned logic vectors and two signed integers under eleven arithmetic, bitwise "
        "and related constraints, and each written with different constants. Every "
        "flavour compiles the same RTL, runs through the same cocotb flow and does one "
        "item per clock edge - only the work under test differs.</p>",
        "<section><dl class=\"env\">",
    ]
    parts += [f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in env_rows]
    parts.append("</dl></section>")

    for classes, group in by_classes(results):
        items = group[0].iterations
        parts.append(f"<h2>{classes} classes, {items} items</h2>")

        # Total run time.
        best_total = fastest(group, "total_s")
        parts.append("<section>")
        parts.append("<h3>Total run time</h3>"
                     "<p class=\"note\">The whole simulation, start to finish.</p>")
        parts.append(
            "<table><thead><tr><th class=\"left\">flavour</th>"
            "<th class=\"left\">what it is</th><th>run (s)</th><th>relative</th>"
            "<th>cpu</th><th>peak rss</th></tr></thead><tbody>")
        for result in sorted(group, key=lambda r: r.total_s if r.ok else 1e18):
            name = f"<code>{esc(name_of(meta, result.flavour))}</code>"
            what = esc(DESCRIPTIONS[result.flavour])
            if not result.ok:
                parts.append(f"<tr><td class=\"left\">{name}</td><td class=\"left\">{what}"
                             f"</td><td colspan=\"4\" class=\"fail\">not measured - "
                             f"{esc(result.detail)}</td></tr>")
                continue
            parts.append(
                f"<tr><td class=\"left\">{name}</td><td class=\"left\">{what}</td>"
                f"<td><b>{result.total_s:.2f}</b></td>"
                f"<td>{result.total_s / best_total:.2f}x</td>"
                f"<td>{result.run.median('cpu_pct'):.0f}%</td>"
                f"<td>{rss_mb(result):.0f} MB</td></tr>")
        parts.append("</tbody></table>")
        chart = svg_bars(group, meta, "total_s", "s", "total run time in seconds")
        parts.append(f"<div class=\"chart\">{chart}</div>")
        parts.append("</section>")

        # Randomization.
        best = fastest(group)
        parts.append("<section>")
        parts.append("<h3>Randomization</h3><p class=\"note\">The same runs with the "
                     "work disabled subtracted from them.</p>")
        parts.append(
            "<table><thead><tr><th class=\"left\">flavour</th><th>baseline (s)</th>"
            "<th>randomizing (s)</th><th>us/item</th><th>cpu us/item</th>"
            "<th>relative</th></tr></thead><tbody>")
        for result in sorted(group, key=lambda r: r.per_item_us if r.ok else 1e18):
            name = f"<code>{esc(name_of(meta, result.flavour))}</code>"
            if not result.ok:
                parts.append(f"<tr><td class=\"left\">{name}</td>"
                             f"<td colspan=\"5\" class=\"fail\">not measured - "
                             f"{esc(result.detail)}</td></tr>")
                continue
            parts.append(
                f"<tr><td class=\"left\">{name}</td>"
                f"<td>{result.baseline.median('real_s'):.2f}</td>"
                f"<td>{result.work_s:.2f}</td>"
                f"<td><b>{result.per_item_us:,.1f}</b></td>"
                f"<td>{result.cpu_per_item_us:,.1f}</td>"
                f"<td>{result.per_item_us / best:.2f}x</td></tr>")
        parts.append("</tbody></table>")
        chart = svg_bars(group, meta, "per_item_us", "us", "microseconds per item")
        parts.append(f"<div class=\"chart\">{chart}</div>")

        pairs = head_to_head(group)
        if pairs:
            parts.append("<div class=\"h2h\">")
            for other, rand, total in pairs:
                rand_figure, rand_word = faster_by(rand)
                total_figure, total_word = faster_by(total)
                parts.append(
                    f"<div><b class=\"{rand_word}\">{rand_figure:.2f}x {rand_word}</b>"
                    f"<span>randomizing, against <code>{esc(name_of(meta, other))}</code>"
                    f" - and {total_figure:.2f}x {total_word} over the whole run</span>"
                    "</div>")
            parts.append("</div>")
        parts.append("</section>")

    parts += [
        "<h2>How it was measured</h2><section class=\"note\">",
        "<p>The total run time is the whole simulation - process startup, elaboration, "
        "cocotb bringup, the class definitions, the loop and the randomization. It is "
        "what a user waits for, and it is why a flavour can win on randomization and "
        "lose on the run.</p>",
        "<p>Each flavour is also run over the same number of clock cycles with the "
        "randomization disabled, and subtracting that leaves the randomization on its "
        "own. Baselines are not expected to agree between flavours, only to be the same "
        "for a flavour's own two phases.</p>",
        "<p>A fresh item is built for every iteration, and the classes are taken in turn, "
        "so no implementation can amortize the analysis of one class across the rest - "
        "which is the position a testbench building one sequence item per transaction is "
        "in.</p>",
        "<p><code>cpu us/item</code> is the same subtraction over user + system time "
        "across the whole process group. A SystemVerilog simulator solves constraints in "
        "a separate SMT solver process which it never reaps, so that time is invisible "
        "to <code>getrusage()</code> and shows up only here. CPU above 100% is real - "
        "solvers use more than one core.</p>",
        "</section>",
        f"<footer>Generated by <code>comparison_benchmark.py</code> on {esc(meta['date'])}. "
        f"Raw runs in <code>summary.csv</code> and <code>results.json</code>.</footer>",
        "</main></body></html>",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def class_counts(text: str) -> list[int]:
    try:
        counts = [int(part) for part in text.split(",") if part.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a list of class counts: {text}") from None
    if not counts or any(n < 1 for n in counts):
        raise argparse.ArgumentTypeError("class counts must be 1 or more")
    return counts


def flavour_list(text: str) -> list[str]:
    chosen = [part.strip() for part in text.split(",") if part.strip()]
    unknown = [f for f in chosen if f not in FLAVOURS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown flavour(s): {', '.join(unknown)} - pick from {', '.join(FLAVOURS)}")
    return [f for f in FLAVOURS if f in chosen]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the local AVL, the released avl-core, pyuvm/pyvsc and "
                    "SystemVerilog on the same constrained-random workload.")
    parser.add_argument("-N", "--classes", type=class_counts, default=None,
                        metavar="N[,N...]",
                        help="how many of the classes take part; a list sweeps them "
                             "(default: all of them)")
    parser.add_argument("-n", "--iterations", type=int, default=None,
                        help="items per run, taken from the classes in turn "
                             f"(default: one of each class, and at least "
                             f"{DEFAULT_ITEMS})")
    parser.add_argument("-r", "--repeats", type=int, default=3,
                        help="timed repeats of each phase, the median is reported "
                             "(default: 3)")
    parser.add_argument("-w", "--warmup", type=int, default=1,
                        help="untimed runs before timing (default: 1)")
    parser.add_argument("--burst", type=int, default=1,
                        help="items per clock edge (default: 1)")
    parser.add_argument("--flavours", type=flavour_list, default=list(FLAVOURS),
                        metavar="LIST", help="flavours to measure, comma separated "
                                             f"(default: {','.join(FLAVOURS)})")
    parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                        help="simulator to use (default: $SIM or verilator)")
    parser.add_argument("--seed", type=int, default=1,
                        help="seed for every flavour's randomization (default: 1)")
    parser.add_argument("--released-version",
                        help="avl-core version to compare against (default: the latest "
                             "on PyPI)")
    parser.add_argument("--pyuvm-version", default=None, metavar="SPEC",
                        help="pyuvm requirement for the local pyuvm environment, e.g. "
                             "'pyuvm==5.0.0' (default: the latest)")
    parser.add_argument("--pyvsc-version", default=None, metavar="SPEC",
                        help="pyvsc requirement for the local pyuvm environment "
                             "(default: the latest)")
    parser.add_argument("--rebuild-env", action="store_true",
                        help="recreate the released and pyuvm environments from scratch")
    parser.add_argument("--work-dir", type=Path, default=HERE / "work",
                        help="where the per-flavour run directories live "
                             "(default: benchmarks/comparison/work)")
    parser.add_argument("--fresh-work", action="store_true",
                        help="remove the run directories first, so every model is "
                             "compiled again")
    parser.add_argument("-o", "--output", type=Path, default=HERE / "results",
                        help="where the report is written (default: "
                             "benchmarks/comparison/results)")
    parser.add_argument("--no-report", action="store_true",
                        help="print the results without writing any files")
    parser.add_argument("--label", help="label recorded with the results and shown in "
                                        "the reports")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="seconds allowed for a single run (default: 3600)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan - flavours, environments and counts - "
                             "then exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show pip output when building the environments")
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if args.warmup < 0:
        parser.error("--warmup must be >= 0")
    if args.burst < 1:
        parser.error("--burst must be >= 1")
    if args.iterations is not None and args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if shutil.which("make") is None:
        parser.error("make not found - source avl.sh from the repository root first")

    # The workload is the classes in rtl/ and cocotb/, so how many there are is
    # a property of the sources rather than something a run chooses.
    available = workload_classes()
    counts = args.classes or [available]
    too_many = [n for n in counts if n > available]
    if too_many:
        parser.error(f"--classes may not exceed the {available} classes in "
                     f"{SOURCES['avl'].name} - asked for "
                     f"{', '.join(str(n) for n in too_many)}")

    flavours = args.flavours
    local_venv = Path(sys.prefix)
    released_version = args.released_version or (
        latest_released() if "released" in flavours else local_version())

    released_dir = HERE / f".venv-released-{released_version}"
    pyuvm_dir = HERE / ".venv-pyuvm"

    released_pins = pinned_versions(Path(sys.executable), RELEASED_PINS)
    pyuvm_pins = pinned_versions(Path(sys.executable), PYUVM_PINS)
    pyuvm_requirements = [args.pyuvm_version or "pyuvm", args.pyvsc_version or "pyvsc"]
    pyuvm_requirements += [f"{name}=={version}" for name, version in pyuvm_pins.items()]
    released_requirements = [f"avl-core=={released_version}"]
    released_requirements += [f"{name}=={version}" for name, version in released_pins.items()]

    if args.dry_run:
        print(f"flavours       : {', '.join(flavours)}")
        print(f"classes        : {', '.join(str(n) for n in counts)} "
              f"(of {available} in the sources)")
        print("items per run  : " + (str(args.iterations) if args.iterations else
                                      f"one of each class, at least {DEFAULT_ITEMS}"))
        print(f"repeats        : {args.warmup} warm-up + {args.repeats} timed, per phase")
        print(f"simulator      : {args.sim}")
        print(f"seed           : {args.seed}")
        if "released" in flavours:
            print(f"released       : {' '.join(released_requirements)}")
            print(f"                 {released_dir}"
                  f"{' (exists)' if released_dir.exists() else ' (would be created)'}")
        if "pyuvm" in flavours:
            print(f"pyuvm          : {' '.join(pyuvm_requirements)}")
            print(f"                 {pyuvm_dir}"
                  f"{' (exists)' if pyuvm_dir.exists() else ' (would be created)'}")
        print(f"work dir       : {args.work_dir}")
        print(f"report         : {'none' if args.no_report else args.output}")
        return 0

    if "released" in flavours:
        ensure_env(released_dir, released_requirements, args.rebuild_env,
                   args.verbose, "released")
    if "pyuvm" in flavours:
        ensure_env(pyuvm_dir, pyuvm_requirements, args.rebuild_env, args.verbose, "pyuvm")

    venvs = {"sv": local_venv, "avl": local_venv,
             "released": released_dir, "pyuvm": pyuvm_dir}
    envs = {flavour: flavour_env(venvs[flavour], args.sim,
                                 isolate_repo=flavour not in ("avl", "sv"), seed=args.seed)
            for flavour in flavours}

    # Which AVL each flavour resolves to, and a guard against two of them
    # silently being the same one. What matters is the working copy in
    # AVL_SOURCE, not the repository as a whole - the released environment lives
    # inside the repository by default, and what is installed in it is a genuine
    # PyPI build.
    versions = {}
    avl_paths = {}
    for flavour in flavours:
        if flavour in ("avl", "released"):
            version, location = describe_avl(venvs[flavour], envs[flavour])
            versions[flavour] = f"avl {version} ({location})"
            avl_paths[flavour] = Path(location).resolve()
        elif flavour == "pyuvm":
            installed = pinned_versions(venv_python(pyuvm_dir), ("pyuvm", "pyvsc", "cocotb"))
            versions[flavour] = ", ".join(f"{k} {v}" for k, v in installed.items())
        else:
            installed = pinned_versions(venv_python(local_venv), ("cocotb",))
            versions[flavour] = f"{args.sim}, cocotb {installed.get('cocotb', 'unknown')}"

    if "avl" in avl_paths and not avl_paths["avl"].is_relative_to(AVL_SOURCE):
        raise SystemExit(
            f"the local environment resolves avl to {avl_paths['avl']}, which is not the "
            f"working copy in {AVL_SOURCE} - source avl.sh from the repository root first")
    if "released" in avl_paths and avl_paths["released"].is_relative_to(AVL_SOURCE):
        raise SystemExit(
            f"the released environment resolves avl to {avl_paths['released']}, which is "
            "the working copy - the two flavours would be identical")

    released_name = f"avl-{released_version}"
    for flavour in flavours:
        print(f"{released_name if flavour == 'released' else flavour:12s}: "
              f"{versions[flavour]}")

    if args.fresh_work and args.work_dir.exists():
        shutil.rmtree(args.work_dir)

    start = time.perf_counter()
    results = []
    for classes in counts:
        iterations = args.iterations or max(classes, DEFAULT_ITEMS)
        print(f"\n{classes} classes, {iterations} items")

        # Serially, never in parallel: two testbenches competing for the same
        # cores would measure each other.
        for flavour in flavours:
            results.append(measure_flavour(
                flavour, classes, iterations, args.burst,
                args.work_dir / flavour, envs[flavour],
                args.sim, args.seed, args.repeats, args.warmup, args.timeout))

    elapsed = time.perf_counter() - start

    names = {flavour: flavour for flavour in flavours}
    if "released" in names:
        names["released"] = f"avl-{released_version}"

    meta = {
        "label": args.label,
        "names": names,
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "flavours": flavours,
        "versions": versions,
        "machine": machine(),
        "simulator": tool_version(args.sim, envs[flavours[0]]),
        "python": sys.version.split()[0],
        "sim": args.sim,
        "seed": args.seed,
        "classes": counts,
        "available_classes": available,
        "iterations": args.iterations,
        "burst": args.burst,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "wall_time_s": elapsed,
    }

    report(results, meta)
    print(f"benchmark took {elapsed / 60.0:.1f} minutes")

    if not args.no_report:
        out = args.output
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(json.dumps(
            {"meta": meta, "results": [r.as_dict() for r in results]}, indent=2))
        write_csv(results, out / "summary.csv")
        markdown(results, meta, out / "RESULTS.md")
        html_report(results, meta, out / "report.html")
        print(f"report written to {out}/report.html, RESULTS.md, summary.csv "
              "and results.json")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

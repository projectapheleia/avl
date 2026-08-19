#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark Environment
#
# What the benchmarks were measured on - the machine, the simulator and the
# packages. A time is only meaningful next to the hardware that produced it and
# the version of the tool that spent it, so every report carries both.
#
# Everything here degrades to "unknown" rather than failing: a report is still
# worth having on a machine whose details cannot be read, or where a simulator
# is not on the PATH by the time the report is written.


from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from functools import cache
from pathlib import Path

# How to ask each tool its version. Keyed by the name cocotb knows the simulator
# by - SIM - which is what every row of results.csv records as its "tool".
VERSION_COMMANDS = {
    "verilator": ["verilator", "--version"],
    "questa": ["vsim", "-version"],
    "modelsim": ["vsim", "-version"],
    "vcs": ["vcs", "-ID"],
    "xcelium": ["xrun", "-version"],
    "icarus": ["iverilog", "-V"],
    "ghdl": ["ghdl", "--version"],
    "nvc": ["nvc", "--version"],
    "riviera": ["vsimsa", "-version"],
}

# Packages whose version changes what is being measured. avl is distributed as
# avl-core; the rest are named as they are imported.
PACKAGES = [("avl", "avl-core"), ("cocotb", "cocotb"), ("pyuvm", "pyuvm"), ("pyvsc", "pyvsc")]

# Fields /proc/cpuinfo may name the processor in, in the order they are tried.
# x86 uses the first; the Arm and POWER kernels use one of the others.
CPU_MODEL_KEYS = ["model name", "cpu model", "hardware", "machine", "cpu"]


def _first_line(text: str | None) -> str | None:
    for line in (text or "").splitlines():
        if line.strip():
            return " ".join(line.split())
    return None


def _run(cmd: list[str]) -> str | None:
    """First line of a version command's output, or None if it cannot be asked.

    Tools disagree about which stream a version belongs on, so both are read and
    whichever spoke first is taken.
    """
    if shutil.which(cmd[0]) is None:
        return None

    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None

    return _first_line(done.stdout) or _first_line(done.stderr)


@cache
def tool_version(tool: str) -> str:
    """Version string of one simulator, as it reports itself."""
    cmd = VERSION_COMMANDS.get(tool)
    if cmd is None:
        return "unknown"

    return _run(cmd) or f"{tool} (not on PATH)"


@cache
def package_version(distribution: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(distribution)
    except PackageNotFoundError:
        return None
    except Exception:  # pragma: no cover - a broken installation is not this tool's problem
        return None


def _cpuinfo() -> list[dict[str, str]]:
    """/proc/cpuinfo, one dictionary per logical processor."""
    try:
        text = Path("/proc/cpuinfo").read_text()
    except OSError:
        return []

    blocks = []
    for chunk in text.split("\n\n"):
        fields = {}
        for line in chunk.splitlines():
            key, sep, value = line.partition(":")
            if sep and value.strip():
                fields[key.strip().lower()] = value.strip()
        if fields:
            blocks.append(fields)
    return blocks


def _sysctl(name: str) -> str | None:
    return _run(["sysctl", "-n", name])


def _linux_cpu() -> dict:
    blocks = _cpuinfo()
    if not blocks:
        return {}

    model = next((blocks[0][k] for k in CPU_MODEL_KEYS if k in blocks[0]), None)

    # A physical core is a (socket, core) pair. Hyperthreads share one, so
    # counting the pairs separates cores from the threads running on them.
    cores = {(b.get("physical id"), b.get("core id"))
             for b in blocks if "core id" in b}

    return {
        "cpu": model,
        "cores": len(cores) or None,
        "threads": len(blocks),
        "sockets": len({b["physical id"] for b in blocks if "physical id" in b}) or None,
    }


def _linux_memory_kb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except (OSError, IndexError, ValueError):
        pass
    return None


def _darwin_cpu() -> dict:
    def count(name):
        value = _sysctl(name)
        return int(value) if value and value.isdigit() else None

    return {
        "cpu": _sysctl("machdep.cpu.brand_string"),
        "cores": count("hw.physicalcpu"),
        "threads": count("hw.logicalcpu"),
        "sockets": count("hw.packages"),
    }


def _darwin_memory_kb() -> int | None:
    value = _sysctl("hw.memsize")
    return int(value) // 1024 if value and value.isdigit() else None


def _clock() -> tuple[str, float] | None:
    """The processor's clock, and which clock it is.

    The maximum a core is allowed to reach is what characterises the machine,
    but it is not always there to be read - a container or a VM, WSL included,
    exposes no cpufreq. What /proc/cpuinfo carries instead is whatever the core
    happened to be running at, which is worth reporting as long as it is not
    labelled as the maximum.
    """
    path = Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
    try:
        return ("max", int(path.read_text().strip()) / 1000.0)
    except (OSError, ValueError):
        pass

    if sys.platform == "darwin":
        hz = _sysctl("hw.cpufrequency_max")
        if hz and hz.isdigit():
            return ("max", int(hz) / 1e6)

    for block in _cpuinfo():
        if "cpu mhz" in block:
            try:
                return ("current", float(block["cpu mhz"]))
            except ValueError:
                break
    return None


def _distribution() -> str:
    """The operating system, as it names itself."""
    if sys.platform == "darwin":
        release = platform.mac_ver()[0]
        return f"macOS {release}" if release else "macOS"

    try:
        pretty = platform.freedesktop_os_release().get("PRETTY_NAME")
        if pretty:
            return pretty
    except (OSError, AttributeError):
        pass

    return f"{platform.system()} {platform.release()}".strip()


def _fmt_cores(cpu: dict) -> str | None:
    cores, threads, sockets = cpu.get("cores"), cpu.get("threads"), cpu.get("sockets")
    if not cores and not threads:
        return None

    if cores and threads and threads != cores:
        text = f"{cores} cores / {threads} threads"
    else:
        text = f"{cores or threads} cores"

    if sockets and sockets > 1:
        text += f" across {sockets} sockets"
    return text


def collect(tools: list[str] | None = None) -> dict:
    """Machine, simulator and package details, for the report to print.

    tools    the simulators the results were produced with - the "tool" column
             of results.csv. Each is asked its version.
    """
    if sys.platform == "darwin":
        cpu, memory_kb = _darwin_cpu(), _darwin_memory_kb()
    elif sys.platform.startswith("linux"):
        cpu, memory_kb = _linux_cpu(), _linux_memory_kb()
    else:  # pragma: no cover - benchmarks are run on Linux and macOS
        cpu, memory_kb = {}, None

    threads = cpu.get("threads") or os.cpu_count()
    clock = _clock()

    machine = {
        "Host": platform.node() or "unknown",
        "Processor": cpu.get("cpu") or platform.processor() or platform.machine() or "unknown",
        "Cores": _fmt_cores({**cpu, "threads": threads}) or "unknown",
        f"Clock ({clock[0]})" if clock else "Clock":
            f"{clock[1] / 1000:.2f} GHz" if clock else None,
        "Memory": f"{memory_kb / (1024 * 1024):.1f} GiB" if memory_kb else "unknown",
        "Architecture": platform.machine() or "unknown",
        "Operating system": _distribution(),
        "Kernel": f"{platform.system()} {platform.release()}",
    }

    simulators = {tool: tool_version(tool) for tool in sorted(tools or [])}

    packages = {"Python": platform.python_version()}
    for name, distribution in PACKAGES:
        found = package_version(distribution)
        if found:
            packages[name] = found

    return {
        # Nothing that could not be read is reported as though it had been.
        "machine": {k: v for k, v in machine.items() if v},
        "simulators": simulators,
        "packages": packages,
    }


def pairs(env: dict) -> list[tuple[str, str]]:
    """Everything collect() found, flattened for printing as a list."""
    items = list(env.get("machine", {}).items())
    items += [(f"Simulator ({tool})", version)
              for tool, version in env.get("simulators", {}).items()]
    items += list(env.get("packages", {}).items())
    return items


def render(env: dict, indent: str = "  ") -> str:
    """The environment as aligned plain text."""
    items = pairs(env)
    width = max((len(label) for label, _ in items), default=0)
    return "\n".join(f"{indent}{label.ljust(width)}  {value}" for label, value in items)


if __name__ == "__main__":
    print(render(collect(sys.argv[1:])))

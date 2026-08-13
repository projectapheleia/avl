#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark - randomization dump
#
# Shared by the cocotb testbenches. When BENCH_DUMP names a file, a testbench
# records every value it drew and writes them out at the end of the run, for
# bench_quality.py to analyse.
#
# Values are collected in memory and written once, rather than appended as they
# are drawn, so that the dump cannot show up in a measurement. Dumping is only
# ever enabled for the quality run, which is untimed, but the timed runs share
# these testbenches and must not pay for it.

from __future__ import annotations

import os


def dump_path() -> str | None:
    """The file to record drawn values in, or None when not dumping."""
    return os.environ.get("BENCH_DUMP") or None


def write_dump(path: str, fields: list[tuple[str, int]], samples: list[tuple[int, ...]]) -> None:
    """Write one row per randomization.

    The header names each field and its width - "a:16,b:16" - so that the
    analysis needs no knowledge of the benchmark it is reading.

    :param path: File to write.
    :param fields: (name, width in bits) per field, in the order of each sample.
    :param samples: One tuple of field values per randomization.
    """
    with open(path, "w") as f:
        f.write(",".join(f"{name}:{width}" for name, width in fields) + "\n")
        for row in samples:
            f.write(",".join(str(int(v)) for v in row) + "\n")

# Copyright 2026 Apheleia
#
# Description:
# Testbench for the AVL logging benchmark.
#
# Logging is the one thing a testbench does on every interesting line, so its
# cost is spread across everything else. Timing is taken in-process with
# perf_counter and printed as JSON, so the simulator, make and import costs are
# not measured.

import json
import logging
import os
import sys
import tempfile
import time

import avl
import cocotb


class Leaf(avl.Component):
    """A component at the bottom of a hierarchy, where a driver or monitor sits."""


def hierarchy(depth):
    """Build a chain of components and return the deepest one."""
    node = avl.Env("env", None)
    for level in range(depth):
        node = Leaf(f"level{level}", node)
    return node


def reset_log_state():
    """Put the log back where it started.

    AVL accumulates every record it has handled, and flushes to file each time
    that reaches the flush level. Both are global, so without this a measurement
    would inherit whatever the one before it left behind and see a different
    number of flushes.
    """
    avl.Log._logdata = {key: [] for key in avl.Log._logdata}
    avl.Log._first = True


def measure(n, fn):
    """Run fn n times from a clean log state, and return the mean per call."""
    fn()
    reset_log_state()
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) / n


def measurements(n):
    """Time each way a testbench writes a log message."""
    shallow = hierarchy(1)
    deep = hierarchy(6)

    # The common case: one INFO from a component, no log file.
    yield "info", measure(n, lambda: shallow.info("transaction accepted"))

    # The same from a deep hierarchy, where the group name costs more to build.
    yield "info_deep", measure(n, lambda: deep.info("transaction accepted"))

    # A message that is below the level, and so should cost almost nothing.
    yield "filtered", measure(n, lambda: shallow.debug("transaction accepted"))

    # A formatted message, as most real ones are.
    count = iter(range(10 ** 9))
    yield "formatted", measure(
        n, lambda: shallow.info(f"transaction {next(count)} accepted, len={4}"))

    # Straight through the Log API, without a component to name the group.
    yield "log_api", measure(n, lambda: avl.Log.info("transaction accepted", "bench"))

    # With a log file set, which is what makes the messages machine readable.
    # Flushing writes through pandas, so the flush level decides how often that
    # cost is paid; the default is used here.
    for suffix in (".csv", ".json", ".txt"):
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            path = handle.name
        avl.Log.set_logfile(path)
        try:
            # Flush once before timing. The first flush of a format imports
            # pandas, and tabulate or yaml with it, and an import is not part of
            # what a message costs - left inside the loop it lands entirely on
            # whichever format is measured first.
            shallow.info("warm")
            avl.Log._flush_log()

            yield f"to_file{suffix.replace('.', '_')}", measure(
                n, lambda: shallow.info("transaction accepted"))
        finally:
            avl.Log.set_logfile(None)
            os.unlink(path)


@cocotb.test
async def test(dut):
    n = int(os.environ.get("AVL_BENCH_N", "2000"))

    # Keep the console quiet: this benchmark measures the cost of handling a
    # message, not of writing thousands of them to a terminal.
    root = logging.getLogger()
    saved = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    for handler in saved:
        root.removeHandler(handler)
    try:
        results = dict(measurements(n))
    finally:
        for handler in saved:
            root.addHandler(handler)

    sys.stdout.write("AVL_BENCH_JSON " + json.dumps(results) + "\n")

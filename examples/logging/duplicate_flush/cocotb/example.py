# Copyright 2026 Apheleia
#
# Description:
# Apheleia logging example - replicates https://github.com/projectapheleia/avl/issues/95
#
# Log._override_cocotb_logging() installs two shutdown paths that both call
# Log._flush_log(): a monkey-patch on cocotb's RegressionManager._log_test_summary,
# and an atexit handler as a fallback for simulators that never reach it.
#
# _flush_log() appends Log._logdata to the file but does not drain it - only
# _avl_callback() clears the buffer, and only when the flush level is reached.
# So whatever is still buffered when the first shutdown path runs is appended a
# second time by the other one. With the default flush level of 1000 records
# that is usually the whole log.
#
# This test calls _flush_log() twice itself, which is exactly what the two
# shutdown paths do, and reads the log file back before the real shutdown
# flushes run. A CSV log is used so that a duplicated record is a duplicated
# row, with none of the repeated-header noise of issue #97.


import csv
from collections import Counter

import avl
import cocotb

_LOGFILE_ = "avl_log.csv"
_MESSAGES_ = 20


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        for i in range(_MESSAGES_):
            self.info(f"Message {i}")


@cocotb.test
async def test(dut):
    # Leave the flush level at its default, so every record is still buffered
    avl.Log.set_logfile(_LOGFILE_)

    e = example_env("env", None)
    await e.start()

    # The two shutdown paths installed by Log._override_cocotb_logging()
    avl.Log._flush_log()
    avl.Log._flush_log()

    with open(_LOGFILE_, newline="") as f:
        counts = Counter(row["Message"] for row in csv.DictReader(f))

    repeated = sorted(m for m, n in counts.items() if n > 1)
    assert not repeated, (
        f"{_LOGFILE_} contains {len(repeated)} duplicated records, the first being "
        f"{repeated[0]!r} - see https://github.com/projectapheleia/avl/issues/95"
    )

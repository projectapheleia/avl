# Copyright 2026 Apheleia
#
# Description:
# Apheleia logging example - replicates https://github.com/projectapheleia/avl/issues/97
#
# Log._flush_log() re-renders the whole in-memory chunk every time it runs, so
# every flush after the first appends another table header. Markdown is the case
# where that is more than cosmetic: a header and its |---|---| separator row
# appearing mid-document ends the table, and every record after it stops being a
# table row at all.
#
# The default flush level is 1000 records, which hides this on short runs. Here
# the flush level is lowered so that several flushes happen while the test is
# still running, and the log is read back before either of the end-of-simulation
# flushes can add a header of its own (issue #95).


import re

import avl
import cocotb

_LOGFILE_ = "avl_log.md"
_FLUSH_LEVEL_ = 10
_MESSAGES_ = 10 * _FLUSH_LEVEL_

_HEADER_ = re.compile(r"\|[-:]+\|(?:[-:]+\|)+")
"""The |---:|:---| separator row under a markdown header. One per table.

The cells hold nothing but dashes and colons, so a row of logged values can
never match, however the flushes end up concatenated.
"""


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        for i in range(_MESSAGES_):
            self.info(f"Message {i}")


@cocotb.test
async def test(dut):
    # Flush often enough that the log file is written several times over
    avl.Log.set_logfile(_LOGFILE_)
    avl.Log.set_flush_level(_FLUSH_LEVEL_)

    e = example_env("env", None)
    await e.start()

    with open(_LOGFILE_) as f:
        log = f.read()

    # A message from the middle of the run, so the check below is looking at a
    # file that more than one flush went into
    _midpoint_ = f"Message {_MESSAGES_ // 2}"
    assert _midpoint_ in log, (
        f"{_LOGFILE_} does not contain {_midpoint_!r}, so the flush level of "
        f"{_FLUSH_LEVEL_} did not flush more than once"
    )

    # One table, one header, however many flushes it took to write it
    headers = _HEADER_.findall(log)
    assert len(headers) == 1, (
        f"{_LOGFILE_} contains {len(headers)} markdown table headers, expected 1 - "
        "see https://github.com/projectapheleia/avl/issues/97"
    )

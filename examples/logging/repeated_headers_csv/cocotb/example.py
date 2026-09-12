# Copyright 2026 Apheleia
#
# Description:
# Apheleia logging example - covers https://github.com/projectapheleia/avl/issues/97
# for the .csv format.
#
# Unlike .txt / .md / .rst, this one passes today. The mechanism is different:
# to_csv() is told header=Log._first, so only the first flush writes the column
# names and later flushes append bare rows. There is nothing to fix here - the
# example is a guard, so that a fix for the formats that do repeat their headers
# cannot quietly regress the one that already gets it right.


import csv

import avl
import cocotb

_LOGFILE_ = "avl_log.csv"
_FLUSH_LEVEL_ = 10
_MESSAGES_ = 10 * _FLUSH_LEVEL_
_COLUMNS_ = ["Time", "Level", "Group", "Message", "Filename", "LineNo"]


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

    with open(_LOGFILE_, newline="") as f:
        rows = list(csv.reader(f))

    # More rows than the flush level, so more than one flush went into the file
    # and the checks below are not passing on a single chunk
    assert len(rows) - 1 > _FLUSH_LEVEL_, (
        f"{_LOGFILE_} holds {len(rows) - 1} records, too few for the flush level "
        f"of {_FLUSH_LEVEL_} to have flushed more than once"
    )

    assert rows[0] == _COLUMNS_, f"{_LOGFILE_} does not start with the column names"

    # One table, one header, however many flushes it took to write it
    repeats = [n for n, row in enumerate(rows[1:], start=2) if row == _COLUMNS_]
    assert not repeats, (
        f"{_LOGFILE_} repeats the header row at line(s) {repeats} - "
        "see https://github.com/projectapheleia/avl/issues/97"
    )

    ragged = [n for n, row in enumerate(rows[1:], start=2) if len(row) != len(_COLUMNS_)]
    assert not ragged, f"{_LOGFILE_} has {len(ragged)} malformed row(s), first at line {ragged[:1]}"

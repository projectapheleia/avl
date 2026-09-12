# Copyright 2026 Apheleia
#
# Description:
# Apheleia logging example - covers https://github.com/projectapheleia/avl/issues/97
# for the .json format.
#
# Unlike .txt / .md / .rst, this one passes today, and the mechanism is different
# again: JSON Lines has no header to repeat, so each flush appends records that
# stand on their own. What multi-flush can still break here is the line
# structure - if a flush ever stops ending its output with a newline, the first
# record of the next flush lands on the same line as the last record of the
# previous one and neither parses. That is a property of pandas' to_json rather
# than of AVL, which is exactly why it is worth pinning down.


import json

import avl
import cocotb

_LOGFILE_ = "avl_log.json"
_FLUSH_LEVEL_ = 10
_MESSAGES_ = 10 * _FLUSH_LEVEL_
_COLUMNS_ = {"Time", "Level", "Group", "Message", "Filename", "LineNo"}


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
        lines = [(n, line.strip()) for n, line in enumerate(f, start=1) if line.strip()]

    # More records than the flush level, so more than one flush went into the
    # file and the checks below are not passing on a single chunk
    assert len(lines) > _FLUSH_LEVEL_, (
        f"{_LOGFILE_} holds {len(lines)} records, too few for the flush level "
        f"of {_FLUSH_LEVEL_} to have flushed more than once"
    )

    # One record per line, whichever flush wrote it
    broken = []
    for n, line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            broken.append(f"line {n}: {e}")
            continue
        if set(record) != _COLUMNS_:
            broken.append(f"line {n}: keys {sorted(record)}")

    assert not broken, (
        f"{_LOGFILE_} is not valid JSON Lines - {len(broken)} bad line(s), first: "
        f"{broken[0]} - see https://github.com/projectapheleia/avl/issues/97"
    )

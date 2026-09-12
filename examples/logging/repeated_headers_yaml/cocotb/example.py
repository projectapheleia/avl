# Copyright 2026 Apheleia
#
# Description:
# Apheleia logging example - covers https://github.com/projectapheleia/avl/issues/97
# for the .yaml format.
#
# Unlike .txt / .md / .rst, this one passes today, by a third mechanism. YAML has
# no header to repeat: each flush dumps its records as sequence items at column
# zero, so appending one dump to another simply continues the same top level
# sequence and the file stays a single document holding every record in order.
#
# What that relies on is the dump staying anonymous - no document start marker,
# no nesting, and a trailing newline so the next flush's first item begins on a
# line of its own. Lose any of those and each flush becomes its own document, or
# the file stops parsing. The example is a guard, so a fix for the formats that
# do repeat their headers cannot quietly regress this one.


import yaml

import avl
import cocotb

_LOGFILE_ = "avl_log.yaml"
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
        log = f.read()

    # One document, however many flushes it took to write it - a flush that
    # started a document of its own would show up here
    documents = list(yaml.safe_load_all(log))
    assert len(documents) == 1, (
        f"{_LOGFILE_} holds {len(documents)} YAML documents, expected 1 - "
        "see https://github.com/projectapheleia/avl/issues/97"
    )

    records = documents[0]
    assert isinstance(records, list), (
        f"{_LOGFILE_} is a {type(records).__name__}, expected one flat sequence of records"
    )

    # More records than the flush level, so more than one flush went into the
    # file and the checks above are not passing on a single chunk
    assert len(records) > _FLUSH_LEVEL_, (
        f"{_LOGFILE_} holds {len(records)} records, too few for the flush level "
        f"of {_FLUSH_LEVEL_} to have flushed more than once"
    )

    malformed = [
        n for n, record in enumerate(records, start=1)
        if not isinstance(record, dict) or set(record) != _COLUMNS_
    ]
    assert not malformed, (
        f"{_LOGFILE_} has {len(malformed)} malformed record(s), first at index {malformed[0]}"
    )

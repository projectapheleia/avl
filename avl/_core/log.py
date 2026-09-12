# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Logging

import atexit
import logging
import os
import re

from cocotb.regression import SimFailure
from cocotb.utils import get_sim_time

from ._lazy import lazy_import

pd = lazy_import("pandas")
tabulate = lazy_import("tabulate")
yaml = lazy_import("yaml")

# Setup Logging
# Done at top level as must be done early to catch all startup messages
# from cocotb

_ANSI_ESCAPE_ = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
"""Colour and cursor control that a console handler adds, which has no place in
a log file. Compiled once, because it is applied to every message logged.
"""

_COLUMN_WIDTHS_ = {
    "Time": 16,
    "Level": 8,
    "Group": 24,
    "Message": 100,
    "Filename": 100,
    "LineNo": 8,
}
_DEFAULT_COLUMN_WIDTH_ = 24
"""How wide to write each column of the formats laid out in columns.

Fixed, rather than sized to the records in hand, because the log is written a
chunk at a time under a single heading - a chunk sized to its own content could
not line up with the one before it. Anything wider is wrapped onto more lines.
"""


class _avl_callback_handler_(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        Log._avl_callback(record)


class Log:
    _logfile = None
    """Where the log is written, and in what format - the extension chooses it.

    None until :meth:`set_logfile` is called, and while it is None the records
    are still collected but never written anywhere.
    """

    _loggers = set()
    """The loggers carrying the callback handler.

    A set, not a list: every message logged asks whether its logger is in here,
    and a testbench has one logger per component.
    """

    _logdata = {"Time": [], "Level": [], "Group": [], "Message": [], "Filename": [], "LineNo": []}
    """The records collected since the last flush, held as one list per column.

    Column oriented because that is the shape a DataFrame is built from, and
    every output format goes through one.
    """

    _flush_level = 1000
    """How many records to collect before writing them out.

    The trade is memory against how often the file is touched, and how much of
    the log survives a simulation that dies without unwinding. See
    :meth:`set_flush_level`.
    """

    _first = True
    """Whether the next flush is the first one.

    The first writes the file and its header; the rest append to it.
    """

    @staticmethod
    def _avl_callback(record: logging.LogRecord) -> None:
        """
        Handles logging callback for AVL (Apheleia Verification Library) system.

        :param record: logging.LogRecord
            The log record to be processed. Contains details such as the log level,
            message, filename, and line number.

        :notes:
            - Control characters (e.g., ANSI escape codes) are removed from the log message.
            - Duplicate records are ignored.
            - When the flush level is reached, the log data is written out and cleared.
        """

        # A record reaches here once per logger in its ancestry that carries the
        # callback handler, because logging propagates it up the hierarchy, and
        # AVL names its groups hierarchically. Marking the record is how the
        # repeats are dropped; scanning a list of the records seen so far costs
        # more with every message logged since the last flush.
        if getattr(record, "_avl_seen_", False):
            return
        record._avl_seen_ = True

        Log._logdata["Time"].append(get_sim_time())
        Log._logdata["Level"].append(record.levelname)
        Log._logdata["Group"].append(record.name)
        Log._logdata["Message"].append(_ANSI_ESCAPE_.sub("", record.getMessage()))
        Log._logdata["Filename"].append(record.pathname)
        Log._logdata["LineNo"].append(record.lineno)

        if len(Log._logdata["Time"]) >= Log._flush_level:
            Log._flush_log()

    @staticmethod
    def _override_cocotb_logging() -> None:
        """
        Overrides the default logging behavior for Cocotb by adding a custom callback handler
        to all existing loggers and ensuring that logs are flushed at the end of the program.

        This function performs the following:
        - Retrieves all loggers from the logging root manager.
        - Adds a custom callback handler (`_avl_callback_handler_`) to each logger.
        - Registers a cleanup function (`Log.at_exit`) to flush all logs at program exit.

        :raises Exception: If there is an issue adding the callback handler or registering the cleanup function.
        """
        if len(Log._loggers) > 0:
            return

        # Add callback to all logger
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        for logger in loggers:
            logger.addHandler(_avl_callback_handler_())
            Log._loggers.add(logger)

        # Some simulators don't call atexit, so we register a cleanup function
        # to ensure that logs are flushed at the end of the program.
        import cocotb.regression
        original_summary = cocotb.regression.RegressionManager._log_test_summary

        def patched_summary(self):
            original_summary(self)
            Log._flush_log()

        cocotb.regression.RegressionManager._log_test_summary = patched_summary

        # Flush all logs at end (fallback)
        atexit.register(Log._flush_log)

    @staticmethod
    def _new_logger(group: str) -> logging.Logger:
        """
        Creates a new logger with the specified group name.

        :param group: Name of the logger group.
        :type group: str
        :return: New logger instance.
        :rtype: logging.Logger
        """
        logger = logging.getLogger(group)
        logger.addHandler(_avl_callback_handler_())
        Log._loggers.add(logger)

        logger.setLevel(logging.INFO)
        return logger

    @staticmethod
    def _fixed_columns(d) -> tuple:
        """
        The headings and widths that pin down the column layout of a chunk.

        tabulate sizes a column to the wider of its heading and its content, so
        padding the heading out to the fixed width and capping the content there
        with ``maxcolwidths`` - which wraps whatever is too long - lays every
        chunk out the same, whatever that chunk happens to hold.

        :param d: The chunk being flushed.
        :type d: pandas.DataFrame
        :return: The padded headings, and the width of each column.
        :rtype: tuple
        """
        widths = [_COLUMN_WIDTHS_.get(c, _DEFAULT_COLUMN_WIDTH_) for c in d.columns]
        return [str(c).ljust(w) for c, w in zip(d.columns, widths)], widths

    @staticmethod
    def _flush_log() -> None:
        """
        Flushes the log data to the specified log file.
        The log data is written in the format specified by the file extension of the log file.
        Supported formats include CSV, JSON, YAML, TXT, Markdown, and reStructuredText (RST).
        The log data is converted to a pandas DataFrame before writing.

        Flushing drains the buffer, so flushing twice writes the records once.
        Both shutdown paths installed by :meth:`_override_cocotb_logging` call
        this, and either of them may be the one that runs.
        """

        if len(Log._logdata["Time"]) == 0:
            return

        if Log._logfile is not None:
            fileext = os.path.splitext(Log._logfile)[1]
            d = pd.DataFrame(Log._logdata)
            mode = "w" if Log._first else "a"

            if fileext == ".csv":
                d = d.replace({r"\t": r"\\t", r"\n": r"\\n"}, regex=True)
                d.to_csv(Log._logfile, mode=mode, header=Log._first, index=False, quoting=1)
            elif fileext == ".json":
                d.to_json(Log._logfile, mode=mode, lines=True, orient="records")
            elif fileext in [".yml", ".yaml"]:
                d = d.replace({r"\t": r"\\t", r"\n": r"\\n"}, regex=True)
                with open(Log._logfile, mode) as f:
                    yaml.dump(
                        d.to_dict(orient="records"), f, default_flow_style=False, width=float("inf")
                    )
            elif fileext == ".txt":
                headers, widths = Log._fixed_columns(d)
                view = tabulate.tabulate(
                    d.values.tolist(), headers=headers, tablefmt="grid", maxcolwidths=widths
                )
                with open(Log._logfile, mode) as f:
                    # After the first chunk, drop the top border, the heading and
                    # the rule beneath it: the rule that closed the last row of
                    # the previous chunk already opens this one.
                    f.write(view if Log._first else "\n".join(view.split("\n")[3:]))
                    f.write("\n")
            elif fileext == ".md":
                headers, widths = Log._fixed_columns(d)
                markdown_view = d.to_markdown(index=False, headers=headers, maxcolwidths=widths)
                assert markdown_view is not None
                with open(Log._logfile, mode) as f:
                    # As above, dropping the heading and the |---| row beneath
                    # it. A table has one of each, and a second pair part way
                    # down ends it - everything after would stop being a table.
                    f.write(
                        markdown_view if Log._first else "\n".join(markdown_view.split("\n")[2:])
                    )
                    f.write("\n")
            elif fileext == ".rst":
                headers, widths = Log._fixed_columns(d)
                view = tabulate.tabulate(
                    d, headers=headers, tablefmt="rst", showindex=False, maxcolwidths=widths
                )
                lines = view.split("\n")
                if Log._first:
                    with open(Log._logfile, mode) as f:
                        f.write(view + "\n")
                else:
                    # The same slice, but a simple table is terminated by its
                    # bottom border, so the rows go over the border that closed
                    # the previous chunk rather than after it. lines[0] is that
                    # border, and it is only ever "=" and spaces.
                    os.truncate(Log._logfile, os.path.getsize(Log._logfile) - (len(lines[0]) + 1))
                    with open(Log._logfile, "a") as f:
                        f.write("\n".join(lines[3:]) + "\n")
            else:
                raise ValueError(f"Unsupported file extension {fileext}")

            Log._first = False

        # Outside the check above, because the buffer has to stay bounded by the
        # flush level whether or not anyone asked for a log file - and a log file
        # is opt-in.
        Log._logdata = {
            "Time": [],
            "Level": [],
            "Group": [],
            "Message": [],
            "Filename": [],
            "LineNo": [],
        }

    @staticmethod
    def set_logfile(logfile: str) -> None:
        """
        Sets the log file for the logger.

        File extension determines the format of the log file.
        Supported formats include CSV, JSON, YAML, TXT, Markdown, and reStructuredText (RST).

        :param logfile: Name of the log file.
        :type logfile: str
        """
        Log._logfile = logfile

    @staticmethod
    def set_flush_level(level: int) -> None:
        """
        Sets the flush level for the logger.

        :param level: Flush level to be set.
        """
        Log._flush_level = level

    @staticmethod
    def debug(msg: str, group: str = "cocotb") -> None:
        """
        Logs a debug message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.debug(msg, stacklevel=2)

    @staticmethod
    def info(msg: str, group: str = "cocotb") -> None:
        """
        Logs an info message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.info(msg, stacklevel=2)

    @staticmethod
    def warn(msg: str, group: str = "cocotb") -> None:
        """
        Logs a warning message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.warning(msg, stacklevel=2)

    @staticmethod
    def warning(msg: str, group: str = "cocotb") -> None:
        """
        Logs a warning message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.warning(msg, stacklevel=2)

    @staticmethod
    def error(msg: str, group: str = "cocotb") -> None:
        """
        Logs an error message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.error(msg, stacklevel=2)

    @staticmethod
    def critical(msg: str, group: str = "cocotb") -> None:
        """
        Logs a critical message.
        Instantly stops the simulation by raising a SimFailure exception.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.critical(msg, stacklevel=2)
        raise SimFailure()

    @staticmethod
    def fatal(msg: str, group: str = "cocotb") -> None:
        """
        Logs a fatal message and raises a SimFailure exception.
        Instantly stops the simulation by raising a SimFailure exception.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        logger = logging.getLogger(group)
        if logger not in Log._loggers:
            logger = Log._new_logger(group)

        logger.fatal(msg, stacklevel=2)
        raise SimFailure()


__all__ = ["Log"]

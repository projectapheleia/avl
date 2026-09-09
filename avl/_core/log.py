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
            Log._logdata = {
                "Time": [],
                "Level": [],
                "Group": [],
                "Message": [],
                "Filename": [],
                "LineNo": [],
            }

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
    def _flush_log() -> None:
        """
        Flushes the log data to the specified log file.
        The log data is written in the format specified by the file extension of the log file.
        Supported formats include CSV, JSON, YAML, TXT, Markdown, and reStructuredText (RST).
        The log data is converted to a pandas DataFrame before writing.
        """

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
                with open(Log._logfile, mode) as f:
                    f.write(
                        tabulate.tabulate(d.values.tolist(), headers=d.columns, tablefmt="grid")
                    )
            elif fileext == ".md":
                with open(Log._logfile, mode) as f:
                    markdown_view = d.to_markdown(index=False)
                    assert markdown_view is not None
                    f.write(markdown_view)
            elif fileext == ".rst":
                with open(Log._logfile, mode) as f:
                    f.write(tabulate.tabulate(d, headers="keys", tablefmt="rst", showindex=False))
            else:
                raise ValueError(f"Unsupported file extension {fileext}")

            Log._first = False

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

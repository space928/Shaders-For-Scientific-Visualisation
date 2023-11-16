#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import sys
from abc import abstractmethod
import io
import logging
from typing import Union, TextIO


# This module provides a basic wrapper around the python logging module, to standardise the logging format and make
# logging code more concise.

class SSVFormatter(logging.Formatter):
    def __init__(self, fmt):
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "raw") and record.raw:
            return record.getMessage()
        else:
            return logging.Formatter.format(self, record)


class SSVLogStream(io.StringIO):
    """
    A StringIO pipe for sending log messages with a severity level.
    """
    @abstractmethod
    def write(self, text: str, severity: int = logging.INFO) -> int:
        """
        Called to write a log message to the stream.

        :param text: the message to log.
        :param severity: the severity to log the message with.
        :return: the number of characters written to the stream.
        """
        ...


class SSVStreamHandler(logging.StreamHandler):
    stream: Union[SSVLogStream, TextIO] = None

    def __init__(self, stream=None):
        super().__init__()
        if stream is not None:
            self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        # Small modification of the build in StreamHandler to pass the log level to the stream
        try:
            msg = self.format(record)
            stream = self.stream
            if issubclass(type(stream), SSVLogStream):
                stream.write(msg + self.terminator, severity=record.levelno)
            else:
                stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


def make_formatter(prefix="pySSV"):
    return SSVFormatter(f"[{prefix}] [%(levelname)s] [%(module)s] [%(funcName)s] %(message)s")


def set_output_stream(stream: TextIO, level=logging.INFO, prefix="pySSV"):
    handler = SSVStreamHandler(stream)
    handler.setFormatter(make_formatter(prefix))
    handler.setLevel(level)
    _ssv_logger.addHandler(handler)


def set_severity(severity: int):
    """
    Sets the minimum message severity to be logged.

    :param severity: the logging severity as an integer. Preset severity levels are defined in the ``logging`` module.
                     Possible values include: ``logging.DEBUG``, ``logging.INFO``, ``logging.WARN``, ``logging.ERROR``,
                     etc...
    """
    _ssv_logger.setLevel(severity)


def get_severity() -> int:
    """
    Gets the minimum severity level of the current logger.

    :return: the minimum severity level of the logger.
    """
    return _ssv_logger.level


def log(msg, *args, severity=logging.DEBUG, raw=False):
    """
    Logs a message to the console.

    :param msg: message to log to the console
    :param args: objects to log to the console
    :param severity: the severity to log the message with, severity levels are defined in the ``logging`` module.
    :param raw: logs the message without any formatting
    """
    _ssv_logger.log(severity, msg, *args, stacklevel=3, extra={"raw": raw})


if "_ssv_logger" not in globals():
    logging.basicConfig()

    _ssv_logger = logging.getLogger("pySSV")
    # Steal all the default log handlers
    # for h in logging.getLogger(None).handlers:
    #     _ssv_logger.addHandler(h)
    _ssv_logger.setLevel(logging.INFO)
    formatter = make_formatter()
    for h in _ssv_logger.handlers:
        h.setFormatter(formatter)

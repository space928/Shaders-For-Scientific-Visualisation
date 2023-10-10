#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

import logging

# This module provides a basic wrapper around the python logging module, to standardise the logging format and make
# logging code more concise.

logging.basicConfig(format="[pySSV] [%(levelname)s] [%(module)s] [%(funcName)s] %(message)s", level=logging.INFO)


def set_severity(severity: int):
    """
    Sets the minimum message severity to be logged.

    :param severity: the logging severity as an integer. Preset severity levels are defined in the ``logging`` module.
                     Possible values include: ``logging.DEBUG``, ``logging.INFO``, ``logging.WARN``, ``logging.ERROR``,
                     etc...
    """
    logging.basicConfig(level=severity)


def log(msg, *args, severity=logging.DEBUG):
    """
    Logs a message to the console.
    :param msg: message to log to the console
    :param args: objects to log to the console
    :param severity: the severity to log the message with, severity levels are defined in the ``logging`` module.
    """
    logging.log(severity, msg, *args)

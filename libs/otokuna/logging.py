import datetime
import logging

LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


class _Iso8601Formatter(logging.Formatter):
    """Formats the datetime of a log record in ISO8601 format.
    If includes the milliseconds and the local timezone.
    """
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, tz=LOCAL_TIMEZONE)
        return dt.isoformat(timespec="milliseconds")


def setup_logger(name, filename=None, include_timestamp=True, propagate=True):
    """Setup logger
    :param name: Name of the logger.
    :param filename: Pass a filename to log to a file too (default is None
        which does not log to a file).
    :param include_timestamp: Whether to include timestamps or not. Set to False when
        logging from AWS Lambda because it already includes timestamps in the logs.
    :param propagate: Whether to propagate to parent loggers or not. Set to False to
        avoid duplicated logs in Lambda.
        See: https://forum.serverless.com/t/python-lambda-logging-duplication-workaround/1585/6
    :return: logger
    """
    logger = logging.getLogger(name)
    loglevel = logging.INFO
    logformat = "%(name)s[%(process)d] %(levelname)s %(message)s"
    if include_timestamp:
        logformat = "%(asctime)s " + logformat
    logger.setLevel(loglevel)
    formatter = _Iso8601Formatter(logformat)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if filename is not None:
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = propagate

    # TODO: figure out how to use coloredlogs with custom formatter
    return logger

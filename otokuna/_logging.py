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


def setup_logger(name, filename=None):
    logger = logging.getLogger(name)
    loglevel = logging.INFO
    logformat = "%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s"
    logger.setLevel(loglevel)
    formatter = _Iso8601Formatter(logformat)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if filename is not None:
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # TODO: figure out how to use coloredlogs with custom formatter
    return logger

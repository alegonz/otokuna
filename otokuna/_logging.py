import logging

import coloredlogs


def setup_logger(name, filename=None):
    logger = logging.getLogger(name)
    loglevel = logging.INFO
    logger.setLevel(loglevel)
    logger.addHandler(logging.StreamHandler())
    log_format = "%(asctime)s.%(msecs)03d %(name)s[%(process)d] %(levelname)s %(message)s"

    if filename is not None:
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    coloredlogs.install(level=loglevel, logger=logger, fmt=log_format, datefmt="%Y-%m-%dT%H:%M:%S%z")
    return logger

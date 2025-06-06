import os
import logging
from logging import Logger
from logging.handlers import RotatingFileHandler


def get_logger() -> Logger:
    logger = logging.getLogger("outpost")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    debug = os.getenv("DEBUG", "0")

    if debug == "1":
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    else:
        file_handler = RotatingFileHandler(
            "/var/log/outpost.log", maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

import logging

from src.logging import VanirFormatter


def logging_setup():
    logger = logging.getLogger("discord")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(VanirFormatter())

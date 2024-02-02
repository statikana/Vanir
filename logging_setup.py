import logging


def logging_setup():
    logging.getLogger("root").setLevel(logging.INFO)
    # logging.getLogger("matplotlib").setLevel(logging.INFO)
    # logging.getLogger("selenium").setLevel(logging.INFO)
    # logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

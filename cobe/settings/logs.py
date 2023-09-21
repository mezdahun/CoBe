import logging

# Settings affecting logging
log_level = logging.INFO
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logger(logger_name):
    """Setting up the logger for the project that can be used in any module"""
    # create logger
    logger = logging.getLogger(logger_name)
    # set log level
    logger.setLevel(log_level)
    # create console handler and set level to debug
    # console_handler = logging.StreamHandler()
    # console_formatter = logging.Formatter(log_format)
    # console_handler.setFormatter(console_formatter)
    # logger.addHandler(console_handler)
    return logger
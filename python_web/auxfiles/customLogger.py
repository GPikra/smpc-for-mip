""" A custom logger class """

import coloredlogs
import logging
from logging.config import fileConfig


class Logger:
    """ A custom logger """

    def __init__(self, loggers):
        # logging.config.fileConfig(
        #     fname="python_web/auxfiles/config/logging.cfg", disable_existing_loggers=False)
        self.__loggers = [logging.getLogger(i) for i in loggers]
        coloredlogs.install(level='DEBUG', logger=self.__loggers[0])
        self.__loggers[0].propagate = False

    def info(self, message):
        [log.info(message) for log in self.__loggers]

    def debug(self, message):
        [log.debug(message) for log in self.__loggers]

    def warning(self, message):
        [log.warning(message) for log in self.__loggers]

    def error(self, message):
        [log.error(message) for log in self.__loggers]

    def critical(self, message):
        [log.critical(message) for log in self.__loggers]

    def exception(self, message):
        [log.exception(message) for log in self.__loggers]

    def log(self, message):
        [log.log(message) for log in self.__loggers]

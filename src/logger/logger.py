from typing import Optional, Dict
import logging
import logging.config
from datetime import datetime
import os

file_handlers: Dict[str, logging.FileHandler] = {}
log_formatter = logging.Formatter(
    '%(levelname)s %(asctime)s %(created)f %(name)s %(module)s [%(processName)s %(threadName)s] '
    '[%(filename)s %(lineno)s %(funcName)s] %(message)s')


class LogFilter(logging.Filter):
    def filter(self, record):
        """only use INFO

        筛选, 只需要 INFO 级别的log

        :param record:
        :return:
        """
        if logging.INFO <= record.levelno < logging.ERROR:
            return super().filter(record)
        else:
            return 0


def _get_filename(*, basename='app.log', log_level='info'):
    date_str = datetime.today().strftime('%Y%m%d')
    pidstr = str(os.getpid())
    return ''.join((
        date_str, '-', pidstr, '-', log_level, '-', basename,))


class LogFactory:
    _SINGLE_FILE_MAX_BYTES = 50 * 1024 * 1024
    _BACKUP_COUNT = 10
    _LOG_CONFIG_DICT = {
        'version': 1,

        'disable_existing_loggers': False,

        'formatters': {
            'dev': {
                'class': 'logging.Formatter',
                'format': ('%(levelname)s %(asctime)s %(created)f %(name)s %(module)s [%(processName)s %(threadName)s] '
                           '[%(filename)s %(lineno)s %(funcName)s] %(message)s')
            },
            'prod': {
                'class': 'logging.Formatter',
                'format': ('%(levelname)s %(asctime)s %(created)f %(name)s %(module)s %(process)d %(thread)d '
                           '[%(filename)s %(lineno)s %(funcName)s] %(message)s')
            }
        },
        'filters': {
            'info_filter': {
                '()': LogFilter,

            }
        },

        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'ERROR',
                'formatter': 'dev'
            },

            'file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': _get_filename(log_level='info'),
                'maxBytes': _SINGLE_FILE_MAX_BYTES,
                'encoding': 'UTF-8',
                'backupCount': _BACKUP_COUNT,
                'formatter': 'dev',
                'delay': True,
                # 'filters': ['info_filter', ]  # only INFO, no ERROR
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': _get_filename(log_level='error'),
                'maxBytes': _SINGLE_FILE_MAX_BYTES,  # 2GB
                'encoding': 'UTF-8',
                'backupCount': _BACKUP_COUNT,
                'formatter': 'dev',
                'delay': True,
            },

        },

        'loggers': {
            'SAMPLE_LOGGER': {
                'handlers': ['console', 'file', 'file_error'],
                'level': 'INFO'
            },
        },
    }

    logging.config.dictConfig(_LOG_CONFIG_DICT)
    @classmethod
    def get_logger(cls, logger_name):
        return logging.getLogger(logger_name)

    @staticmethod
    def _get_file_logger_handler(filename: str):
        handler = file_handlers.get(filename, None)
        if handler is None:
            handler = logging.FileHandler(filename)
            file_handlers[filename] = handler
        return handler

    @staticmethod
    def get_file_logger(filename: str):
        """
        return a logger that writes records into a file.
        """
        logger = logging.getLogger(filename)
        handler = LogFactory._get_file_logger_handler(filename)  # get singleton handler.
        handler.setFormatter(log_formatter)
        logger.addHandler(handler)  # each handler will be added only once.
        return logger


if __name__ == "__main__":
    sample_logger = LogFactory.get_file_logger(_get_filename())
    sample_logger.info("Hello world")
    sample_logger.error("error")
    print(_get_filename())

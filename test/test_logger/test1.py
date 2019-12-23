from src.logger import LogFactory
from src.logger import _get_filename

if __name__ == "__main__":
    # logger = LogFactory.get_file_logger(_get_filename(log_level="info"))
    logger = LogFactory.get_logger("SAMPLE_LOGGER")
    logger.error("2error")
    logger.info("2info")
    logger.debug("2debug")
    debug = LogFactory.get_logger("DEBUG_LOGGER")
    debug.debug("1debug")
    debug.info("1info")
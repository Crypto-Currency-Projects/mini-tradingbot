from src.logger import LogFactory
from src.logger import _get_filename

if __name__ == "__main__":
    logger = LogFactory.get_file_logger(_get_filename(log_level="info"))
    logger.error("12312")
    logger.info("test")
    logger.info("test")

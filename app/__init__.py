from loguru import logger
import sys

logger.remove()

logger.add(
    sink=sys.stdout,
    level="INFO",
    colorize=True,
    format="{time:DD.MM.YY — HH:mm:ss} | <level>{level}</level> | <yellow>{file}</yellow> : <cyan>{line}</cyan> | {message}",
)

logger.add(
    "logs.log",
    rotation="10 MB",
    retention="2 days",
    compression="zip",
    level="INFO",
    format="{time:DD.MM.YY — HH:mm:ss} | {level} | {file}:{line} | {message}",
)

__all__ = ["logger"]
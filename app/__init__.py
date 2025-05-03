from loguru import logger

logger.add(
    "logs.log",
    rotation="10 MB",
    retention="15 days",
    compression="zip",
    level="INFO"
)

__all__ = ["logger"]
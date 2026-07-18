import logging
import sys


def setup_logging(level: str = "INFO", fmt: str = "json") -> logging.Logger:
    logger = logging.getLogger("parallelmind")

    if fmt == "json":
        try:
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                jsonlogger.JsonFormatter(
                    fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                )
            )
            logger.addHandler(handler)
        except ImportError:
            fmt = "standard"

    if fmt != "json":
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
        )

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger

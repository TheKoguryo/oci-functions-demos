import logging
import os

mylogger = logging.getLogger()
mylogger.setLevel(level=os.getenv("FN_LOG_LEVEL", 'INFO'))

class PrefixAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra['prefix']}] {msg}", kwargs

def setLoggerPrefix(prefix):
    logger = logging.getLogger()

    global mylogger
    mylogger = PrefixAdapter(logger, {"prefix": prefix})
    mylogger.setLevel(level=os.getenv("FN_LOG_LEVEL", 'INFO'))


def getLogger():
    return mylogger


def get_env_variable(name, cast_type=str):
    value = os.getenv(name)

    if value is None:
        raise ValueError(f"Environment variable '{name}' not set")

    try:
        return cast_type(value)
    except ValueError:
        raise ValueError(f"Environment variable '{name}' could not be converted to {cast_type}")

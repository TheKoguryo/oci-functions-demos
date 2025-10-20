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


def model_to_details(source_obj, target_class, exclude_fields=None, extra_fields=None):
    exclude_fields = exclude_fields or []
    extra_fields = extra_fields or {}

    source_dict = {
        k: getattr(source_obj, k)
        for k in source_obj.attribute_map.keys()
        if hasattr(source_obj, k) and k not in exclude_fields
    }

    source_dict.update(extra_fields)

    return target_class(**source_dict)
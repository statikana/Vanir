from datetime import timedelta, datetime, UTC
from functools import lru_cache, wraps


def timed_lru_cache(seconds: int, maxsize: int = 128):

    def wrapper_cache(func):

        func = lru_cache(maxsize=maxsize)(func)

        func.lifetime = timedelta(seconds=seconds)

        func.expiration = datetime.now(tz=UTC) + func.lifetime


        @wraps(func)

        def wrapped_func(*args, **kwargs):

            if datetime.now(tz=UTC) >= func.expiration:

                func.cache_clear()

                func.expiration = datetime.now(tz=UTC) + func.lifetime


            return func(*args, **kwargs)


        return wrapped_func


    return wrapper_cache
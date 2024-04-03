from datetime import UTC, datetime, timedelta
from functools import lru_cache, wraps
from typing import Any, Callable, TypeVar

RetT = TypeVar("RetT")
FuncT = Callable[..., RetT]


def timed_lru_cache(seconds: int, maxsize: int = 128) -> Callable[[FuncT], FuncT]:
    def wrapper_cache(func: FuncT) -> FuncT:
        func = lru_cache(maxsize=maxsize)(func)

        func.lifetime = timedelta(seconds=seconds)

        func.expiration = datetime.now(tz=UTC) + func.lifetime

        @wraps(func)
        def wrapped_func(*args: Any, **kwargs: Any) -> RetT:
            if datetime.now(tz=UTC) >= func.expiration:
                func.cache_clear()

                func.expiration = datetime.now(tz=UTC) + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache

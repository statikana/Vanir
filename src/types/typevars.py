from typing import Coroutine, TypeVar, Any

T = TypeVar("T")

CoroT = Coroutine[Any, Any, T]

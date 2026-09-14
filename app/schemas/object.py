from pydantic import BaseModel
from typing import TypeVar, Any, Literal

T = TypeVar("T", default=Any)


class SubscribeObject[T](BaseModel):
    type: str
    pattern: str | None = None
    channel: str
    data: T


class KaraokeSubData[T](BaseModel):
    type: Literal["status", "highest"]
    data: T

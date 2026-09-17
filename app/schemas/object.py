from pydantic import BaseModel
from typing import TypeVar, Any, Literal

T = TypeVar("T", default=Any)

KaraokePubType = Literal["status", "highest", "sync"]


class SubscribeObject[T](BaseModel):
    type: str
    pattern: str | None = None
    channel: str
    data: T


class KaraokeSubData[T](BaseModel):
    type: KaraokePubType
    data: T

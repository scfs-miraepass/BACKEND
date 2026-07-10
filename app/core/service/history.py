from app.schemas import PointHistory

from core.core import ServiceCore
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    _Type = PointHistory
else:
    _Type = object


class PointHistory(ServiceCore, _Type):
    def __new__(cls, payload) -> PointHistory | None:
        if payload is None:
            return None
        return super().__new__(cls)

    def __init__(self, payload: PointHistory | None):
        super().__init__()
        self._payload = payload

    def __str__(self):
        return str(self._payload)

    def __repr__(self):
        return repr(self._payload)

    def __getattribute__(self, name):
        if name == "_payload":
            return super().__getattribute__(name)

        payload = super().__getattribute__("_payload")
        if hasattr(payload, name):
            return getattr(payload, name)
        return super().__getattribute__(name)

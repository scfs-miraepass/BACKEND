from app.schemas import PointHistory

from core.core import ServiceCore
from typing import TYPE_CHECKING

_Type = PointHistory if TYPE_CHECKING else object


class PointHistory(ServiceCore[PointHistory], _Type): ...

from typing import TYPE_CHECKING

from app.schemas import Quests

from ..core import ServiceCore


if TYPE_CHECKING:
    _Type = Quests
else:
    _Type = object


class Quest(ServiceCore[Quests], _Type): ...

from typing import TYPE_CHECKING
from app.schemas import KaraokePartis

from ...core import ServiceCore

if TYPE_CHECKING:
    _Type = KaraokePartis
else:
    _Type = object


class KaraokeParty(ServiceCore[KaraokePartis], _Type): ...

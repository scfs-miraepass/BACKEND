from typing import TYPE_CHECKING
from app.schemas import KaraokeBids

from app.core.core import ServiceCore

if TYPE_CHECKING:
    _Type = KaraokeBids
else:
    _Type = object


class KaraokeBid(ServiceCore[KaraokeBids], _Type): ...

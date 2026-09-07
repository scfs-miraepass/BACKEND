from typing import TYPE_CHECKING

from app.schemas import Karaokes

from ..core import ServiceCore

if TYPE_CHECKING:
    _Type = Karaokes
else:
    _Type = object


class Karaoke(ServiceCore[Karaokes], _Type):
    # TODO
    ...

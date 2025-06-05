import datetime
from typing import TypedDict

# All values converted to fixed point int's for transmission
class FixedPositionSample(TypedDict):
    latitude: int
    longitude: int
    extra: int
    flags: int
    time: int

class PositionSample(TypedDict):
    latitude: float
    longitude: float
    speed: float | None
    altitude: float | None
    time: datetime.datetime
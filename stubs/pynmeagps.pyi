from typing import Any, Tuple, Optional, Protocol
from io import IOBase
from datetime import date
from datetime import time

class NMEAMessage(Protocol):
    msgID: str
    lat: Optional[float]
    lon: Optional[float]
    spd: Optional[float]
    alt: Optional[float]
    date: Optional[date]
    time: Optional[time]

class NMEAReader:
    def __init__(
        self, 
        stream: IOBase,
        *,
        validate: int = ...,
        msgmode: int = ...,
        parsebitfield: bool = ...,
        scaling: bool = ...,
        **kwargs: Any
    ) -> None: ...
    
    def read(self) -> Tuple[bytes, Optional[NMEAMessage]]:
        ...
    
    def parse(
        self, 
        data: bytes, 
        validate: int = ..., 
        msgmode: int = ...,
        **kwargs: Any
    ) -> NMEAMessage: ...

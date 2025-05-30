from typing import Any, Optional, Tuple
from typing_extensions import Self
from aiocoap.numbers.types import Type
from aiocoap.resource import Site

class Message:
    payload: bytes
    code: Any
    token: Optional[bytes]
    def __init__(
        self, 
        payload: bytes = ..., 
        mtype: int = ..., 
        code: Any = ..., 
        uri: Optional[str] = ...
    ) -> None: ...

class Context:
    async def request(self, message: Message) -> Message: ...
    async def shutdown(self) -> None: ...

    @classmethod
    async def create_server_context(self, root: Site, bind: Tuple[str, int]) -> Self: ...


CON, NON, ACK, RST = Type.CON, Type.NON, Type.ACK, Type.RST
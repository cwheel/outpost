from typing import Optional
from typing import Tuple
from typing import Awaitable
from typing_extensions import Self
from aiocoap.numbers.types import Type
from aiocoap.resource import Site
from aiocoap.numbers.codes import Code

class Message:
    payload: bytes
    code: Code
    token: Optional[bytes]
    mtype: int

    def __init__(
        self, 
        payload: bytes = ..., 
        mtype: int = ..., 
        code: Code = ..., 
        uri: Optional[str] = ...
    ) -> None: ...
    
    def get_request_uri(self) -> str: ...

class Request:
    response: Awaitable[Message]

class Context:
    def request(self, message: Message) -> Request: ...
    async def shutdown(self) -> None: ...

    @classmethod
    async def create_server_context(self, root: Site, bind: Tuple[str, int]) -> Self: ...
    
    @classmethod
    async def create_client_context(self) -> Self: ...


CON, NON, ACK, RST = Type.CON, Type.NON, Type.ACK, Type.RST

POST = Code(2)
INTERNAL_SERVER_ERROR = Code(160)
UNAUTHORIZED = Code(129)
METHOD_NOT_ALLOWED = Code(133)
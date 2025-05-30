import asyncio
import signal
import sys
import os
import aiocoap
from aiocoap.resource import Resource
from aiocoap.resource import Site
from aiocoap import Message
from typing_extensions import Self

from outpost.logger import get_logger

logger = get_logger()

class HealthResource(Resource):
    async def render_get(self, request: Message) -> Message:
        return aiocoap.Message(payload=b'{"status": "healthy"}')

class PositionResource(Resource):
    async def render_post(self, request: Message) -> Message:
        logger.info('POST /p')
        return aiocoap.Message(mtype=aiocoap.ACK)

class OutpostServer:
    def __init__(self: Self, host: str = '0.0.0.0', port: int = 5683) -> None:
        self.host = host
        self.port = port
        self.context: aiocoap.Context | None = None
        self.shutdown_event = asyncio.Event()
        
    async def setup_resources(self: Self) -> Site:
        root = Site()

        root.add_resource(['health'], HealthResource())
        root.add_resource(['p'], PositionResource())
        return root
    
    async def start(self: Self) -> None:
        try:
            root = await self.setup_resources()
            bind_address = (self.host, self.port)
            
            self.context = await aiocoap.Context.create_server_context(
                root, bind=bind_address
            )
            logger.info(f"outpost server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    async def stop(self: Self) -> None:
        logger.info("Shutting down the outpost server...")

        if self.context:
            await self.context.shutdown()

        self.shutdown_event.set()
    
    async def run(self: Self) -> None:
        await self.start()

        loop = asyncio.get_running_loop()
        
        def signal_handler() -> None:
            logger.info("Received shutdown signal!")
            asyncio.create_task(self.stop())
        
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

        await self.shutdown_event.wait()

async def main() -> None:
    host = os.getenv('OUTPOST_HOST', '0.0.0.0')
    port = int(os.getenv('OUTPOST_PORT', '5683'))
    
    server = OutpostServer(host=host, port=port)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
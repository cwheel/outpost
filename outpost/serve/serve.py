import asyncio
import signal
import sys
import os
import aiocoap
from aiocoap.resource import Site
from aiocoap import Message
from typing_extensions import Self

from outpost.batch import unpack_batch
from outpost.serve.database import create_database_client
from outpost.serve.database import PostgreSQLClient
from outpost.serve.secured_resource import SecureResource
from outpost.logger import get_logger
from outpost.crypto import load_psk


logger = get_logger()


class HealthResource(SecureResource):
    def __init__(self, db_client: PostgreSQLClient, psk: bytes):
        super().__init__(psk)
        self.db_client = db_client

    async def secure_render_get(self, _: Message) -> Message:
        if self.db_client.is_healthy():
            return aiocoap.Message(payload=b"{'status': 'healthy'}")
        else:
            return aiocoap.Message(payload=b"{'status': 'unhealthy'}")


class PositionResource(SecureResource):
    def __init__(self, db_client: PostgreSQLClient, psk: bytes):
        super().__init__(psk)
        self.db_client = db_client
    
    async def secure_render_post(self, request: Message) -> Message:
        try:
            batch = unpack_batch(request.payload)

            if batch:
                await self.db_client.insert_positions_batch(batch)
                logger.info(f'Saved {len(batch)} positions to database')

            return aiocoap.Message(mtype=aiocoap.ACK)
        except Exception as e:
            logger.error(f'Error processing positions: {e}')
            return aiocoap.Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)


class OutpostServer:
    def __init__(self: Self, host: str, port: int, database_url: str, psk: bytes) -> None:
        self.host = host
        self.port = port
        self.database_url = database_url
        self.psk = psk
        self.context: aiocoap.Context | None = None
        self.db_client: PostgreSQLClient | None = None
        self.shutdown_event = asyncio.Event()
        
    async def setup_resources(self: Self) -> Site:
        root = Site()
        
        if not self.db_client:
            raise RuntimeError("Database client not initialized")

        root.add_resource(['health'], HealthResource(self.db_client, self.psk))
        root.add_resource(['p'], PositionResource(self.db_client, self.psk))
        return root
    
    async def start(self: Self) -> None:
        try:
            self.db_client = await create_database_client(self.database_url)
            logger.info('Database connection established')
            
            root = await self.setup_resources()
            bind_address = (self.host, self.port)
            
            self.context = await aiocoap.Context.create_server_context(
                root, bind=bind_address
            )
            logger.info(f'outpost server started on {self.host}:{self.port}')
        except Exception as e:
            logger.error(f'Failed to start server: {e}')
            raise
    
    async def stop(self: Self) -> None:
        logger.info('Shutting down the outpost server...')

        if self.context:
            await self.context.shutdown()
            
        if self.db_client:
            await self.db_client.disconnect()
            logger.info('Database connection closed')

        self.shutdown_event.set()
    
    async def run(self: Self) -> None:
        await self.start()

        loop = asyncio.get_running_loop()
        
        def signal_handler() -> None:
            logger.info('Received shutdown signal!')
            asyncio.create_task(self.stop())
        
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

        await self.shutdown_event.wait()


async def main() -> None:
    host = os.getenv('OUTPOST_HOST', '0.0.0.0')
    port = int(os.getenv('OUTPOST_PORT', '5683'))
    database_url = os.getenv('DATABASE_URL', 'postgresql://outpost:outpost@postgres/outpost')
    
    psk = None
    psk_path = os.getenv('OUTPOST_PSK')

    if psk_path is None:
        logger.error(f'Failed to load PSK, none provided')
        return

    try:
        psk = load_psk(psk_path)
        logger.info(f'Loaded PSK from {psk_path}')
    except Exception as e:
        logger.error(f'Failed to load PSK: {e}')
        sys.exit(1)
    
    server = OutpostServer(host, port, database_url, psk)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info('Server stopped by user')
    except Exception as e:
        logger.error(f'Server error: {e}')
        sys.exit(1)
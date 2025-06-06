import asyncio
from typing import List, Optional
import asyncpg
from asyncpg import Pool

from outpost.logger import get_logger
from outpost.position import PositionSample


logger = get_logger()


class PostgreSQLClient:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[Pool] = None
        
    async def connect(self) -> None:
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            
            logger.info('Connected to PostgreSQL with pool')
            await self.setup_schema()
            
        except Exception as e:
            logger.error(f'Failed to connect to PostgreSQL: {e}')
            raise
    
    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def setup_schema(self) -> None:
        setup_sql = """
        CREATE EXTENSION IF NOT EXISTS postgis;
        
        CREATE TABLE IF NOT EXISTS position (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            location GEOMETRY(POINT, 4326) NOT NULL,
            speed DOUBLE PRECISION,
            altitude DOUBLE PRECISION,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_position_timestamp ON position(timestamp);
        CREATE INDEX IF NOT EXISTS idx_position_location ON position USING GIST(location);
        """
        
        if not self.pool:
            raise RuntimeError('Database not connected')
        
        async with self.pool.acquire() as conn:
            await conn.execute(setup_sql)
            logger.info('Position table schema verified')
    
    async def insert_positions_batch(self, samples: List[PositionSample]) -> List[int]:
        if not self.pool:
            raise RuntimeError("Database not connected")
            
        if not samples:
            return []
            
        insert_sql = """
        INSERT INTO position (timestamp, location, speed, altitude)
        VALUES ($1, ST_Point($2, $3, 4326), $4, $5)
        RETURNING id
        """
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                inserted_ids = []
                for sample in samples:
                    row = await conn.fetchrow(
                        insert_sql,
                        sample['time'],
                        sample['longitude'],
                        sample['latitude'],
                        sample['speed'],
                        sample['altitude']
                    )

                    if row is None:
                        raise RuntimeError('INSERT did not return a row')
                    
                    inserted_ids.append(row['id'])
                
                return inserted_ids
    
    async def is_healthy(self) -> bool:
        if not self.pool:
            return False
            
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
                return True
        except Exception as e:
            logger.error(f'Database health check failed: {e}')
            return False

async def create_database_client(database_url: str) -> PostgreSQLClient:
    client = PostgreSQLClient(database_url)
    await client.connect()
    return client
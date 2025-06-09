import pytest
import aiocoap
from datetime import datetime
from unittest import mock
from outpost.serve.serve import HealthResource
from outpost.serve.serve import PositionResource
from outpost.batch import pack_batch

@pytest.fixture
def mock_db_client():
    db_client = mock.MagicMock()
    db_client.is_healthy.return_value = True
    db_client.insert_positions_batch = mock.AsyncMock()
    return db_client

@pytest.fixture
def health_resource(mock_db_client, test_psk):
    return HealthResource(mock_db_client, test_psk)

@pytest.fixture
def position_resource(mock_db_client, test_psk):
    return PositionResource(mock_db_client, test_psk)

@pytest.fixture
def sample_batch():
    base_time = datetime.fromtimestamp(1640995200)
    return [
        {
            "time": base_time,
            "latitude": 44.46556321397201,
            "longitude": -72.68754208675988,
            "speed": 25.0,
            "altitude": None
        },
        {
            "time": base_time,
            "latitude": 44.46557,
            "longitude": -72.68755,
            "speed": 30.0,
            "altitude": None
        }
    ]

class TestServerSmoke:
    @pytest.mark.asyncio
    async def test_health_resource_healthy(self, health_resource, mock_db_client):
        # Test the secure method directly since encryption/decryption is handled by parent class
        mock_request = mock.MagicMock()
        response = await health_resource.secure_render_get(mock_request)
        
        assert response.payload == b"{'status': 'healthy'}"
        mock_db_client.is_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_resource_unhealthy(self, health_resource, mock_db_client):
        mock_db_client.is_healthy.return_value = False
        
        mock_request = mock.MagicMock()
        response = await health_resource.secure_render_get(mock_request)
        
        assert response.payload == b"{'status': 'unhealthy'}"

    @pytest.mark.asyncio
    async def test_position_resource_success(self, position_resource, mock_db_client, sample_batch):
        # Pack the batch for the test
        packed_data = pack_batch(sample_batch)
        
        mock_request = mock.MagicMock()
        mock_request.payload = packed_data
        
        response = await position_resource.secure_render_post(mock_request)
        
        assert response.mtype == aiocoap.ACK
        mock_db_client.insert_positions_batch.assert_called_once()
        
        # Verify the unpacked data was passed to the database
        call_args = mock_db_client.insert_positions_batch.call_args[0][0]
        assert len(call_args) == 2
        assert abs(call_args[0]["latitude"] - 44.46556321397201) < 1e-7

    @pytest.mark.asyncio
    async def test_position_resource_invalid_data(self, position_resource, mock_db_client):
        mock_request = mock.MagicMock()
        mock_request.payload = b"invalid_data"
        
        response = await position_resource.secure_render_post(mock_request)
        
        assert response.code == aiocoap.INTERNAL_SERVER_ERROR
        mock_db_client.insert_positions_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_position_resource_empty_batch(self, position_resource, mock_db_client):
        # Test with empty batch - should handle gracefully
        with mock.patch('outpost.serve.serve.unpack_batch', return_value=[]):
            mock_request = mock.MagicMock()
            mock_request.payload = b"empty_batch"
            
            response = await position_resource.secure_render_post(mock_request)
            
            assert response.mtype == aiocoap.ACK
            mock_db_client.insert_positions_batch.assert_not_called()
import pytest
from unittest import mock
from datetime import datetime
from outpost.client.client import OutpostClient

@pytest.fixture
def sample_position():
    return {
        "time": datetime.fromtimestamp(1640995200),
        "latitude": 44.46556321397201,
        "longitude": -72.68754208675988,
        "speed": 25.0,
        "altitude": None
    }

@pytest.fixture
def client_config(test_psk):
    return {
        "device": "/dev/ttyUSB0",
        "baud": 9600,
        "outpost_host": "localhost:5683",
        "psk": test_psk,
        "similarity_threshold": 0.0001
    }


class TestClient:
    def test_client_start(self, client_config):
        with mock.patch(
            'threading.Thread'
        ) as mock_thread, mock.patch(
            'outpost.client.client.BatchProcessingTask'
        ) as mock_batch_task, mock.patch(
            'outpost.client.client.PositionCollectionTask'
        ) as mock_collection_task:
            client = OutpostClient(**client_config)
            client.start()
            
            # Verify tasks are started
            mock_collection_task.return_value.start.assert_called_once()
            mock_batch_task.return_value.start.assert_called_once()
            
            # Verify threads are created and started
            assert mock_thread.call_count == 2
            assert mock_thread.return_value.start.call_count == 2

    def test_client_stop(self, client_config):
        with mock.patch(
            'outpost.client.client.BatchProcessingTask'
        ) as mock_batch_task, mock.patch(
            'outpost.client.client.PositionCollectionTask'
        ) as mock_collection_task:
            client = OutpostClient(**client_config)
            
            client.stop()
            
            # Verify tasks are stopped
            mock_collection_task.return_value.stop.assert_called_once()
            mock_batch_task.return_value.stop.assert_called_once()

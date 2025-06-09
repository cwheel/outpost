import pytest
from datetime import datetime, timedelta
from outpost.batch import pack_batch, unpack_batch


# Test location constants (Stowe, Vermont)
BASE_LAT = 44.46556321397201
BASE_LON = -72.68754208675988
BASE_TIME = datetime.fromtimestamp(1640995200)  # 2022-01-01 00:00:00 UTC


@pytest.fixture
def sample_data():
    """Basic sample data for batch testing"""
    return [
        {
            "time": BASE_TIME,
            "latitude": BASE_LAT,
            "longitude": BASE_LON,
            "speed": 25.0,
            "altitude": None
        },
        {
            "time": BASE_TIME + timedelta(seconds=30),
            "latitude": BASE_LAT + 0.001,
            "longitude": BASE_LON + 0.001,
            "speed": 30.0,
            "altitude": None
        },
        {
            "time": BASE_TIME + timedelta(seconds=60),
            "latitude": BASE_LAT + 0.002,
            "longitude": BASE_LON + 0.002,
            "altitude": 150.0,
            "speed": None
        }
    ]


class TestBatch:
    def test_basic_round_trip(self, sample_data):
        packed = pack_batch(sample_data)
        unpacked = unpack_batch(packed)
        
        assert len(unpacked) == len(sample_data)
        
        for i, (original, result) in enumerate(zip(sample_data, unpacked)):
            assert result["time"] == original["time"], f"Time mismatch at index {i}"

            # Allow for reasonable precision loss in coordinates
            assert abs(result["latitude"] - original["latitude"]) < 0.01, f"Latitude mismatch at index {i}"
            assert abs(result["longitude"] - original["longitude"]) < 0.01, f"Longitude mismatch at index {i}"

    def test_sample_sorting(self, sample_data):
        # Reverse the order of existing samples to test sorting
        unordered_samples = list(reversed(sample_data))
        
        packed = pack_batch(unordered_samples)
        unpacked = unpack_batch(packed)
        
        # Should be sorted by time (same as original sample_data order)
        for i, expected_sample in enumerate(sample_data):
            assert unpacked[i]["time"] == expected_sample["time"]

    def test_empty_batch_error(self):
        with pytest.raises(IndexError):
            pack_batch([])

    def test_single_sample_batch(self, sample_data):
        single_sample = [sample_data[0]]
        
        packed = pack_batch(single_sample)
        unpacked = unpack_batch(packed)
        
        assert len(unpacked) == 1
        assert unpacked[0]["time"] == sample_data[0]["time"]

    def test_data_type_preservation(self, sample_data):
        # Use first two samples from fixture, which already have speed (first) and altitude (third)
        mixed_samples = [sample_data[0], sample_data[2]]
        
        packed = pack_batch(mixed_samples)
        unpacked = unpack_batch(packed)
        
        assert len(unpacked) == 2

        # First sample should have speed, no altitude
        assert unpacked[0]["speed"] is not None
        assert unpacked[0]["altitude"] is None

        # Second sample should have altitude, no speed
        assert unpacked[1]["speed"] is None
        assert unpacked[1]["altitude"] is not None
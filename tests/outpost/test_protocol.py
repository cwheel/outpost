import pytest
from datetime import datetime
from outpost.protocol import (
    pack_header, unpack_header, pack_sample, unpack_sample, to_fixed, samples_can_be_in_same_batch,
    OUTPOST_BATCH_MAGIC_HEADER, OUTPOST_BATCH_VERSION, OUTPOST_HEADER_WIDTH,
    OUTPOST_SAMPLE_WIDTH, FLAG_HAS_ALTITUDE, FLAG_HAS_SPEED
)
from outpost.position import PositionSample, FixedPositionSample


# Test location constants (Stowe, Vermont)
TEST_LAT = 44.46556321397201
TEST_LON = -72.68754208675988
TEST_LAT_FIXED = int(TEST_LAT * 10_000_000)
TEST_LON_FIXED = int(TEST_LON * 10_000_000)
TEST_TIMESTAMP = 1640995200  # 2022-01-01 00:00:00 UTC


@pytest.fixture
def base_sample():
    """Base position sample for testing"""
    return {
        "time": datetime.fromtimestamp(TEST_TIMESTAMP),
        "latitude": TEST_LAT,
        "longitude": TEST_LON,
        "speed": 25.0,
        "altitude": None
    }


@pytest.fixture
def sample_with_speed():
    """Sample with speed data"""
    return {
        "time": datetime.fromtimestamp(TEST_TIMESTAMP),
        "latitude": TEST_LAT,
        "longitude": TEST_LON,
        "speed": 25.5,
        "altitude": None
    }


@pytest.fixture
def sample_with_altitude():
    """Sample with altitude data"""
    return {
        "time": datetime.fromtimestamp(TEST_TIMESTAMP),
        "latitude": TEST_LAT,
        "longitude": TEST_LON,
        "speed": None,
        "altitude": 150.7
    }


@pytest.fixture
def precision_sample():
    """Sample with minimum precision values"""
    return {
        "time": datetime.fromtimestamp(TEST_TIMESTAMP),
        "latitude": 0.0000001,
        "longitude": -0.0000001,
        "speed": 0.01,
        "altitude": None
    }


@pytest.fixture
def reference_fixed_sample():
    """Reference fixed-point sample for delta calculations"""
    return FixedPositionSample(
        time=TEST_TIMESTAMP,
        latitude=TEST_LAT_FIXED,
        longitude=TEST_LON_FIXED,
        extra=0,
        flags=0
    )


class TestProtocol:
    @pytest.mark.parametrize("sample_count,extra_data", [
        (5, b""),
        (3, b"extra_data_here"),
    ])
    def test_pack_header(self, sample_count, extra_data):
        packed = pack_header(TEST_TIMESTAMP, TEST_LAT_FIXED, TEST_LON_FIXED, sample_count)
        
        assert len(packed) == OUTPOST_HEADER_WIDTH
        
        full_payload = packed + extra_data
        
        unpacked_timestamp, unpacked_lat, unpacked_lon, unpacked_count, remaining = unpack_header(full_payload)
        assert unpacked_timestamp == TEST_TIMESTAMP
        assert unpacked_lat == TEST_LAT_FIXED
        assert unpacked_lon == TEST_LON_FIXED
        assert unpacked_count == sample_count
        assert remaining == extra_data

    def test_unpack_header_invalid_magic(self):
        valid_header = pack_header(TEST_TIMESTAMP, TEST_LAT_FIXED, TEST_LON_FIXED, 1)

        # Replace first 2 bytes (magic header) with invalid value
        bad_header = b"\xDE\xAD" + valid_header[2:]
        
        with pytest.raises(ValueError, match="Invalid magic number"):
            unpack_header(bad_header)

    def test_unpack_header_invalid_version(self):
        valid_header = pack_header(TEST_TIMESTAMP, TEST_LAT_FIXED, TEST_LON_FIXED, 1)

        # Replace version byte (at offset 2) with invalid value
        bad_header = valid_header[:2] + b"\x63" + valid_header[3:]  # 0x63 = 99
        
        with pytest.raises(ValueError, match="Unsupported version: 99"):
            unpack_header(bad_header)

    def test_pack_sample(self, reference_fixed_sample):
        time_delta = 30
        lat_delta = 100
        lon_delta = -50
        flags = FLAG_HAS_SPEED
        extra_absolute = 2500  # 25.00 km/h

        packed = pack_sample(time_delta, lat_delta, lon_delta, flags, extra_absolute)
        
        assert len(packed) == OUTPOST_SAMPLE_WIDTH
        
        unpacked_sample, remaining = unpack_sample(packed, reference_fixed_sample)

        assert unpacked_sample["flags"] == flags
        assert unpacked_sample["time"] == reference_fixed_sample["time"] + time_delta
        assert unpacked_sample["latitude"] == reference_fixed_sample["latitude"] + (lat_delta * 1000)
        assert unpacked_sample["longitude"] == reference_fixed_sample["longitude"] + (lon_delta * 1000)
        assert unpacked_sample["extra"] == extra_absolute
        assert remaining == b""

    def test_unpack_sample(self, reference_fixed_sample):
        flags = FLAG_HAS_ALTITUDE
        time_delta = 60
        lat_delta = 200
        lon_delta = -100
        extra = 150  # 150m altitude
        
        # Use protocol function to pack the sample
        packed = pack_sample(time_delta, lat_delta, lon_delta, flags, extra)
        sample_data = packed + b"remaining_data"
        
        result_sample, remaining = unpack_sample(sample_data, reference_fixed_sample)
        
        assert result_sample["flags"] == flags
        assert result_sample["time"] == reference_fixed_sample["time"] + time_delta
        assert result_sample["latitude"] == reference_fixed_sample["latitude"] + (lat_delta * 1000)
        assert result_sample["longitude"] == reference_fixed_sample["longitude"] + (lon_delta * 1000)
        assert result_sample["extra"] == extra
        assert remaining == b"remaining_data"

    @pytest.mark.parametrize("sample_fixture,expected_flag,expected_extra", [
        ("sample_with_speed", FLAG_HAS_SPEED, 2550),  # 25.5 * 100
        ("sample_with_altitude", FLAG_HAS_ALTITUDE, 150),  # int(150.7)
    ])
    def test_to_fixed_with_extra_data(self, sample_fixture, expected_flag, expected_extra, request):
        # Get the fixture by name
        sample = request.getfixturevalue(sample_fixture)
        fixed = to_fixed(sample)
        
        assert fixed["time"] == TEST_TIMESTAMP
        assert fixed["latitude"] == TEST_LAT_FIXED
        assert fixed["longitude"] == TEST_LON_FIXED
        assert fixed["flags"] == expected_flag
        assert fixed["extra"] == expected_extra

    def test_to_fixed_precision(self, precision_sample):
        fixed = to_fixed(precision_sample)
        
        assert fixed["latitude"] == 1
        assert fixed["longitude"] == -1
        assert fixed["extra"] == 1  # 0.01 * 100

class TestBatchCompatibility:
    @pytest.fixture
    def compatible_sample(self, base_sample):
        """Sample that's compatible with base_sample"""
        return {
            "time": datetime.fromtimestamp(TEST_TIMESTAMP + 30),  # 30 seconds later
            "latitude": TEST_LAT + 0.001,  # Small coordinate change
            "longitude": TEST_LON + 0.001,
            "speed": 30.0,
            "altitude": None
        }

    @pytest.fixture
    def time_overflow_sample(self, base_sample):
        """Sample with time delta that causes overflow"""
        return {
            "time": datetime.fromtimestamp(TEST_TIMESTAMP + 65000),  # 65000 seconds later
            "latitude": TEST_LAT,
            "longitude": TEST_LON,
            "speed": 30.0,
            "altitude": None
        }

    @pytest.fixture
    def coordinate_overflow_sample(self, base_sample):
        """Sample with coordinate delta that causes overflow"""
        return {
            "time": datetime.fromtimestamp(TEST_TIMESTAMP + 30),  # 30 seconds later
            "latitude": TEST_LAT + 4.0,  # Large coordinate change that causes overflow
            "longitude": TEST_LON,
            "speed": 30.0,
            "altitude": None
        }

    @pytest.fixture
    def boundary_sample(self, base_sample):
        """Sample at the boundary of what's allowed"""
        return {
            "time": datetime.fromtimestamp(TEST_TIMESTAMP + 32767),  # Maximum valid time delta
            "latitude": TEST_LAT + 3.2767,  # Maximum valid coordinate delta (32767/1000/10)
            "longitude": TEST_LON,
            "speed": 30.0,
            "altitude": None
        }

    def test_samples_can_be_in_same_batch_valid(self, base_sample, compatible_sample):
        assert samples_can_be_in_same_batch(base_sample, compatible_sample) == True

    def test_samples_can_be_in_same_batch_time_overflow(self, base_sample, time_overflow_sample):
        assert samples_can_be_in_same_batch(base_sample, time_overflow_sample) == False

    def test_samples_can_be_in_same_batch_coordinate_overflow(self, base_sample, coordinate_overflow_sample):
        assert samples_can_be_in_same_batch(base_sample, coordinate_overflow_sample) == False

    def test_samples_can_be_in_same_batch_boundary_values(self, base_sample, boundary_sample):
        assert samples_can_be_in_same_batch(base_sample, boundary_sample) == True
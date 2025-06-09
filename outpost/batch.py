from typing import List
from datetime import datetime

from outpost.position import PositionSample
from outpost.position import FixedPositionSample
from outpost.protocol import pack_header
from outpost.protocol import pack_sample
from outpost.protocol import unpack_header
from outpost.protocol import unpack_sample
from outpost.protocol import to_fixed
from outpost.protocol import FLAG_HAS_ALTITUDE
from outpost.protocol import FLAG_HAS_SPEED


def pack_batch(batch: List[PositionSample]) -> bytes:
    # Sort samples by timestamp
    sorted_batch = sorted(batch, key=lambda position: position["time"])

    # Extract reference point (first chronologically)
    ref_sample = sorted_batch[0]
    ref_timestamp = int(ref_sample["time"].timestamp())
    ref_lat_fixed = int(ref_sample["latitude"] * 10_000_000)  # 10^7 precision
    ref_lon_fixed = int(ref_sample["longitude"] * 10_000_000)

    # Pack header
    header = pack_header(ref_timestamp, ref_lat_fixed, ref_lon_fixed, len(sorted_batch))

    # Convert all samples to fixed-point representation
    fixed_samples = [to_fixed(sample) for sample in sorted_batch]

    packed_samples = b""
    previous_sample = FixedPositionSample(
        latitude=ref_lat_fixed,
        longitude=ref_lon_fixed,
        time=ref_timestamp,
        extra=0,
        flags=0,
    )

    for i, sample in enumerate(fixed_samples):
        # Calculate coordinate deltas (except for first sample)
        if i == 0:
            lat_delta = 0
            lon_delta = 0
            time_delta = 0
        else:
            # Reduced precision (to 10^4) for delta compression
            lat_delta = int((sample["latitude"] - previous_sample["latitude"]) / 1000)
            lon_delta = int((sample["longitude"] - previous_sample["longitude"]) / 1000)

            time_delta = sample["time"] - previous_sample["time"]

            # Check coordinate deltas fit in 16-bit signed range
            if not (-32768 <= lat_delta <= 32767):
                raise OverflowError(
                    f"Latitude delta {lat_delta} exceeds 16-bit signed range"
                )

            if not (-32768 <= lon_delta <= 32767):
                raise OverflowError(
                    f"Longitude delta {lon_delta} exceeds 16-bit signed range"
                )

            if not (-32768 <= time_delta <= 32767):
                raise OverflowError(
                    f"Time delta {time_delta} exceeds 16-bit signed range"
                )

            previous_sample = sample

        sample_data = pack_sample(
            time_delta, lat_delta, lon_delta, sample["flags"], sample["extra"]
        )
        packed_samples += sample_data

    return header + packed_samples


def unpack_batch(packed_data: bytes) -> List[PositionSample]:
    ref_timestamp, ref_lat_fixed, ref_lon_fixed, sample_count, packed_samples = (
        unpack_header(packed_data)
    )

    samples = []
    previous_sample = FixedPositionSample(
        # Keep as fixed point integers for calculations
        latitude=ref_lat_fixed,
        longitude=ref_lon_fixed,
        time=ref_timestamp,
        extra=0,
        flags=0,
    )

    for _ in range(sample_count):
        sample, packed_samples = unpack_sample(packed_samples, previous_sample)

        has_speed = bool(sample["flags"] & FLAG_HAS_SPEED)
        has_altitude = bool(sample["flags"] & FLAG_HAS_ALTITUDE)

        decoded_sample: PositionSample = {
            "latitude": sample["latitude"] / 10_000_000.0,
            "longitude": sample["longitude"] / 10_000_000.0,
            "speed": sample["extra"] / 100.0 if has_speed else None,
            "altitude": float(sample["extra"]) if has_altitude else None,
            "time": datetime.fromtimestamp(sample["time"]),
        }

        samples.append(decoded_sample)

        previous_sample = sample

    return samples

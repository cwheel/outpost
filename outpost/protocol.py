import struct
from typing import Tuple
from outpost.position import PositionSample
from outpost.position import FixedPositionSample

# Protocol constants
OUTPOST_BATCH_MAGIC_HEADER = 0xA5A5
OUTPOST_BATCH_VERSION = 0x01
OUTPOST_HEADER_WIDTH = 16  # in bytes
OUTPOST_SAMPLE_WIDTH = 9  # in bytes

# Flag bits for data type
FLAG_HAS_ALTITUDE = 0x0
FLAG_HAS_SPEED = 0x01


def to_fixed(sample: PositionSample) -> FixedPositionSample:
    timestamp = int(sample["time"].timestamp())

    # 10^7 precision
    lat_fixed = int(sample["latitude"] * 10_000_000)
    lon_fixed = int(sample["longitude"] * 10_000_000)

    speed = sample.get("speed")
    altitude = sample.get("altitude")

    if speed is not None:
        flags = FLAG_HAS_SPEED
        extra_fixed = int(speed * 100)  # 0.01 km/h precision
    elif altitude is not None:
        flags = FLAG_HAS_ALTITUDE
        extra_fixed = int(altitude)  # 1m precision

    return FixedPositionSample(
        time=timestamp,
        latitude=lat_fixed,
        longitude=lon_fixed,
        extra=extra_fixed,
        flags=flags,
    )


def pack_sample(
    time_delta: int, lat_delta: int, lon_delta: int, flags: int, extra_absolute: int
) -> bytes:
    return struct.pack(
        ">BHhhh",
        flags,  # 1 byte:  Flags
        time_delta,  # 2 bytes: Time delta
        lat_delta,  # 2 bytes: Lat delta
        lon_delta,  # 2 bytes: Lon delta
        extra_absolute,  # 2 bytes: Absolute speed or altitude
    )


def pack_header(
    ref_timestamp: int, ref_lat_fixed: int, ref_lon_fixed: int, sample_count: int
) -> bytes:
    return struct.pack(
        ">HBiiiB",
        OUTPOST_BATCH_MAGIC_HEADER,  # 2 bytes: Protocol
        OUTPOST_BATCH_VERSION,  # 1 byte: Protocol Version
        ref_timestamp,  # 4 bytes: Base timestamp
        ref_lat_fixed,  # 4 bytes: Reference latitude
        ref_lon_fixed,  # 4 bytes: Reference longitude
        sample_count,  # 1 byte: Sample count
    )


def unpack_header(payload: bytes) -> Tuple[int, int, int, int, bytes]:
    header_data = struct.unpack(">HBiiiB", payload[:OUTPOST_HEADER_WIDTH])
    (
        protocol,
        protocol_version,
        ref_timestamp,
        ref_lat_fixed,
        ref_lon_fixed,
        sample_count,
    ) = header_data

    if protocol != OUTPOST_BATCH_MAGIC_HEADER:
        raise ValueError("Invalid magic number")

    if protocol_version != OUTPOST_BATCH_VERSION:
        raise ValueError(f"Unsupported version: {protocol_version}")

    return (
        ref_timestamp,
        ref_lat_fixed,
        ref_lon_fixed,
        sample_count,
        payload[OUTPOST_HEADER_WIDTH:],
    )


def unpack_sample(
    samples: bytes, reference: FixedPositionSample
) -> Tuple[FixedPositionSample, bytes]:
    flags, time_delta, lat_delta, lon_delta, extra = struct.unpack(
        ">BHhhh", samples[:OUTPOST_SAMPLE_WIDTH]
    )

    return (
        FixedPositionSample(
            time=reference["time"] + time_delta,
            latitude=(lat_delta * 1000) + reference["latitude"],
            longitude=(lon_delta * 1000) + reference["longitude"],
            extra=extra,
            flags=flags,
        ),
        samples[OUTPOST_SAMPLE_WIDTH:],
    )

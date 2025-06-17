import logging
import queue
import datetime
from typing import cast, Optional
from pynmeagps import NMEAReader

# Serial seems to be very sensitive to it's installation, and usually
# fails to load on a Github runner
try:
    from serial import Serial
except ImportError:
    Serial = None  # type: ignore

from outpost.position import PositionSample

# Maximum number of samples to queue for submission at once
MAXIMUM_SAMPLES = 500000


class PositionCollectionTask:
    def __init__(
        self,
        device: str,
        baud: int,
        sample_queue: queue.Queue[PositionSample],
        similarity_threshold: float = 0.0001,
    ):
        self.device = device
        self.baud = baud
        self.sample_queue = sample_queue
        self.similarity_threshold = similarity_threshold
        self.last_sample: Optional[PositionSample] = None
        self.running = False

    def _is_similar_position(self, new_sample: PositionSample) -> bool:
        if self.last_sample is None:
            return False

        lat_diff = abs(new_sample["latitude"] - self.last_sample["latitude"])
        lon_diff = abs(new_sample["longitude"] - self.last_sample["longitude"])

        return (
            lat_diff < self.similarity_threshold
            and lon_diff < self.similarity_threshold
        )

    def run(self) -> None:
        current_date: datetime.date | None = None

        try:
            with Serial(self.device, self.baud, timeout=3) as stream:
                nmr = NMEAReader(stream)

                while self.running:
                    try:
                        _, message = nmr.read()
                    except Exception as e:
                        logging.debug(f"Error reading NMEA data: {e}")
                        continue

                    if message is not None:
                        sample = None

                        if message.msgID == "RMC":
                            # If this message has a malformed date, skip it and wait for one with a valid date
                            if message.date is None or message.date == "":
                                continue

                            current_date = message.date

                            sample = PositionSample(
                                latitude=cast(float, message.lat),
                                longitude=cast(float, message.lon),
                                speed=cast(float, message.spd),
                                altitude=None,
                                time=datetime.datetime.combine(
                                    current_date, cast(datetime.time, message.time)
                                ),
                            )
                        elif message.msgID == "GGA" and current_date is not None:
                            sample = PositionSample(
                                latitude=cast(float, message.lat),
                                longitude=cast(float, message.lon),
                                speed=None,
                                altitude=cast(float, message.alt),
                                time=datetime.datetime.combine(
                                    current_date, cast(datetime.time, message.time)
                                ),
                            )

                        if sample and not self._is_similar_position(sample):
                            # Remove the oldest sample if queue is full
                            if self.sample_queue.qsize() > MAXIMUM_SAMPLES:
                                self.sample_queue.get_nowait()
                                logging.info(
                                    "Queue at maximum size, throwing away oldest sample"
                                )

                            self.sample_queue.put(sample)
                            self.last_sample = sample

                            logging.info(f"Added sample to queue: {sample}")

        except Exception as e:
            logging.error(f"Error in collection thread: {e}")
        finally:
            logging.info("Collection thread stopped")

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

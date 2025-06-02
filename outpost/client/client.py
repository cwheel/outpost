import logging
import argparse
import threading
import queue
import time
import datetime
from threading import Thread
from typing import TypedDict
from typing import Optional
from typing import cast
from serial import Serial
from pynmeagps import NMEAReader

logging.getLogger('pynmeagps').setLevel(logging.CRITICAL)

class PositionSample(TypedDict):
    latitude: float
    longitude: float
    speed: float | None
    altitude: float | None
    time: datetime.datetime

class OutpostClient:
    def __init__(self, device: str, baud: int, similarity_threshold: float = 0.0001):
        self.device = device
        self.baud = baud
        self.similarity_threshold = similarity_threshold
        self.sample_queue: queue.Queue[PositionSample] = queue.Queue()
        self.last_sample: Optional[PositionSample] = None
        self.running = False
        
        self.collection_thread: Thread | None = None
        self.processing_thread: Thread | None = None
    
    def is_similar_position(self, new_sample: PositionSample) -> bool:
        if self.last_sample is None:
            return False
        
        lat_diff = abs(new_sample['latitude'] - self.last_sample['latitude'])
        lon_diff = abs(new_sample['longitude'] - self.last_sample['longitude'])
        
        return lat_diff < self.similarity_threshold and lon_diff < self.similarity_threshold
    
    def collect_samples(self) -> None:
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
                        
                        if message.msgID == 'RMC':
                            current_date = cast(datetime.date, message.date)

                            sample = PositionSample(
                                latitude=cast(float, message.lat),
                                longitude=cast(float, message.lon),
                                speed=cast(float, message.spd),
                                altitude=None,
                                time=datetime.datetime.combine(
                                    current_date,
                                    cast(datetime.time, message.time)
                                ),
                            )
                        elif message.msgID == 'GGA' and current_date is not None:
                            sample = PositionSample(
                                latitude=cast(float, message.lat),
                                longitude=cast(float, message.lon),
                                speed=None,
                                altitude=cast(float, message.alt),
                                time=datetime.datetime.combine(
                                    current_date,
                                    cast(datetime.time, message.time)
                                ),
                            )
                        
                        if sample and not self.is_similar_position(sample):
                            self.sample_queue.put(sample)
                            self.last_sample = sample
                            logging.info(f"Added sample to queue: {sample}")
        
        except Exception as e:
            logging.error(f"Error in collection thread: {e}")
        finally:
            logging.info("Collection thread stopped")
    
    def process_samples(self) -> None:
        while self.running or not self.sample_queue.empty():
            try:
                sample = self.sample_queue.get(timeout=1)
                self.send_sample(sample)
                self.sample_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing sample: {e}")
        
        logging.info("Processing thread stopped")
    
    def send_sample(self, sample: PositionSample) -> None:
        print(sample)
    
    def start(self) -> None:
        self.running = True
        
        # Start collection thread
        self.collection_thread = threading.Thread(target=self.collect_samples, daemon=True)
        self.collection_thread.start()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self.process_samples, daemon=True)
        self.processing_thread.start()
        
        logging.info(f"Outpost started on {self.device} at {self.baud} baud")
    
    def stop(self) -> None:
        if not self.running:
            return
        
        self.running = False
        
        # Wait for threads to finish
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        logging.info("Outpost stopped")

def main() -> None:
    parser = argparse.ArgumentParser(description='Outpost Client')
    parser.add_argument('--gps', '-g', default='/dev/ttyGPS0', help='Serial device path (default: /dev/ttyGPS0)')
    parser.add_argument('--baud', '-b', type=int, default=38400, help='Baud rate (default: 38400)')
    parser.add_argument('--threshold', '-t', type=float, default=0.0001, help='Position similarity threshold (default: 0.0001)')
    parser.add_argument('--debug', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    log_level = logging.INFO if args.debug else logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    outpost = OutpostClient(args.gps, args.baud, args.threshold)
    
    try:
        outpost.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        outpost.stop()

if __name__ == '__main__':
    main()
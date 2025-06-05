import logging
import argparse
import threading
import queue
import time
import datetime
import asyncio
from threading import Thread
from typing import TypedDict
from typing import Optional
from typing import cast
from typing import List
from serial import Serial
from pynmeagps import NMEAReader
import aiocoap

from outpost.batch import pack_batch

logging.getLogger('pynmeagps').setLevel(logging.CRITICAL)

# Maximum number of samples to queue for submission at once
MAXIMUM_SAMPLES = 500000

# Minimum number of samples to submit in a batch at once
MINIUM_BATCH_SIZE = 5

# Maximum number of samples to submit in a batch at once
MAXIMUM_BATCH_SIZE = 40

class PositionSample(TypedDict):
    latitude: float
    longitude: float
    speed: float | None
    altitude: float | None
    time: datetime.datetime

class OutpostClient:
    def __init__(self, device: str, baud: int, outpost_host: str, similarity_threshold: float = 0.0001):
        self.device = device
        self.baud = baud
        self.outpost_host = outpost_host
        self.similarity_threshold = similarity_threshold
        self.sample_queue: queue.Queue[PositionSample] = queue.Queue()
        self.last_sample: Optional[PositionSample] = None
        self.running = False
        self.sending = False
        self.send_lock = threading.Lock()
        
        self.collection_thread: Thread | None = None
        self.processing_thread: Thread | None = None
    
    def _is_similar_position(self, new_sample: PositionSample) -> bool:
        if self.last_sample is None:
            return False
        
        lat_diff = abs(new_sample['latitude'] - self.last_sample['latitude'])
        lon_diff = abs(new_sample['longitude'] - self.last_sample['longitude'])
        
        return lat_diff < self.similarity_threshold and lon_diff < self.similarity_threshold
    
    def _collect_samples(self) -> None:
        current_date: datetime.date | None = None

        try:
            with Serial(self.device, self.baud, timeout=3) as stream:
                nmr = NMEAReader(stream)
                
                while self.running:
                    try:
                        _, message = nmr.read()
                    except Exception as e:
                        logging.debug(f'Error reading NMEA data: {e}')
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
                        
                        if sample and not self._is_similar_position(sample):
                            # Remove the oldest sample in the queue to make room for the next sample
                            if self.sample_queue.qsize() > MAXIMUM_SAMPLES:
                                self.sample_queue.get_nowait()
                                logging.info('Queue at maximum size, throwing away oldest sample')

                            self.sample_queue.put(sample)
                            self.last_sample = sample
                            
                            logging.info(f'Added sample to queue: {sample}')
        
        except Exception as e:
            logging.error(f'Error in collection thread: {e}')
        finally:
            logging.info('Collection thread stopped')
    
    def _process_samples(self) -> None:
        batch: List[PositionSample] = []

        while self.running:
            # Wait if we're currently sending a batch
            while self.sending and self.running:
                time.sleep(0.1)
    
            while len(batch) < MAXIMUM_BATCH_SIZE:
                # If we don't have any more samples, but we do have enough for a batch stop trying
                # to collect more - we'll send another batch later
                if self.sample_queue.empty() and len(batch) >= MINIUM_BATCH_SIZE:
                    break

                try:
                    batch.append(self.sample_queue.get())
                    self.sample_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f'Error processing sample: {e}')

            if batch:
                self._send_sample_batch(batch)
                batch = []
            
        logging.info('Processing thread stopped')
    
    def _send_sample_batch(self, samples: List[PositionSample]) -> None:
        if not samples:
            return
            
        with self.send_lock:
            self.sending = True
            
        try:
            batch = pack_batch(samples)
            
            # Run the async CoAP operation in a new event loop
            asyncio.run(self._send_batch_with_retry(batch))
        finally:
            with self.send_lock:
                self.sending = False
    
    async def _send_batch_with_retry(self, batch_data: bytes) -> None:
        context = await aiocoap.Context.create_client_context()
        
        while self.running:
            try:
                request = aiocoap.Message(
                    code=aiocoap.POST,
                    payload=batch_data,
                    uri=f"{self.outpost_host}/p"
                )
                
                # Send with 60 second timeout
                response = await asyncio.wait_for(
                    context.request(request).response,
                    timeout=60.0
                )
                
                if response.code.is_successful():
                    break
                else:
                    logging.warning(f'Server responded with error: {response.code}, retrying...')
                    
            except asyncio.TimeoutError:
                logging.warning('CoAP request timed out after 60 seconds, retrying...')
            except Exception as e:
                logging.error(f'CoAP send error: {e}, retrying...')
            
            # Wait a bit before retrying to avoid overwhelming the server
            await asyncio.sleep(5.0)
        
        await context.shutdown()
    
    def start(self) -> None:
        self.running = True
        
        # Start collection thread
        self.collection_thread = threading.Thread(target=self._collect_samples, daemon=True)
        self.collection_thread.start()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_samples, daemon=True)
        self.processing_thread.start()
        
        logging.info(f'Outpost started on {self.device} at {self.baud} baud')
    
    def stop(self) -> None:
        if not self.running:
            return
        
        self.running = False
        
        # Wait for threads to finish
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        logging.info('Outpost stopped')

def main() -> None:
    parser = argparse.ArgumentParser(description='Outpost Client')
    parser.add_argument('--gps', '-g', default='/dev/ttyGPS0', help='Serial device path (default: /dev/ttyGPS0)')
    parser.add_argument('--baud', '-b', type=int, default=38400, help='Baud rate (default: 38400)')
    parser.add_argument('--server', '-s', required=True, help='Outpost server host (e.g., coap://outpost.example.com:5683)')
    parser.add_argument('--threshold', '-t', type=float, default=0.0001, help='Position similarity threshold (default: 0.0001)')
    parser.add_argument('--debug', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    log_level = logging.INFO if args.debug else logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    outpost = OutpostClient(args.gps, args.baud, args.server, args.threshold)
    
    try:
        outpost.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logging.info('Shutting down...')
    finally:
        outpost.stop()

if __name__ == '__main__':
    main()
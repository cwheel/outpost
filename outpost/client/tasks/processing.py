import logging
import queue
import time
import threading
import asyncio
from typing import List
import aiocoap

from outpost.position import PositionSample
from outpost.batch import pack_batch
from outpost.crypto import encrypt_payload, CryptoError

# Minimum number of samples to submit in a batch at once
MINIMUM_BATCH_SIZE = 5

# Maximum number of samples to submit in a batch at once
MAXIMUM_BATCH_SIZE = 40


class BatchProcessingTask:
    def __init__(self, sample_queue: queue.Queue[PositionSample], 
                 outpost_host: str, psk: bytes, send_lock: threading.Lock):
        self.sample_queue = sample_queue
        self.outpost_host = outpost_host
        self.psk = psk
        self.send_lock = send_lock
        self.running = False
        self.sending = False
    
    def _is_sending(self) -> bool:
        with self.send_lock:
            return self.sending
    
    def _set_sending(self, sending: bool) -> None:
        with self.send_lock:
            self.sending = sending
    
    def run(self) -> None:
        batch: List[PositionSample] = []
        
        while self.running:
            # Wait if we're currently sending a batch
            while self._is_sending() and self.running:
                time.sleep(0.1)
            
            while len(batch) < MAXIMUM_BATCH_SIZE:
                # If we don't have any more samples, but we do have enough for a batch,
                # stop trying to collect more - we'll send another batch later
                if self.sample_queue.empty() and len(batch) >= MINIMUM_BATCH_SIZE:
                    break
                
                try:
                    batch.append(self.sample_queue.get())
                    self.sample_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f'Error processing sample: {e}')
            
            if batch:
                self._set_sending(True)
                try:
                    self._send_batch(batch)
                finally:
                    self._set_sending(False)
                batch = []
        
        logging.info('Processing thread stopped')
    
    def start(self) -> None:
        self.running = True
    
    def stop(self) -> None:
        self.running = False
    
    def _send_batch(self, samples: List[PositionSample]) -> None:
        if not samples:
            return
        
        try:
            batch = pack_batch(samples)
            
            try:
                encrypted_batch = encrypt_payload(batch, self.psk)
            except CryptoError as e:
                logging.error(f'Encryption failed: {e}')
                return
            
            # Run the async CoAP operation in a new event loop
            asyncio.run(self._send_batch_with_retry(encrypted_batch))
        except Exception as e:
            logging.error(f'Error preparing batch for sending: {e}')
    
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
                    logging.info(f'Batch sent successfully: {response.code}')
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
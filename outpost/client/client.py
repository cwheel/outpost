import logging
import argparse
import threading
import queue
import time
import json
from threading import Thread

from outpost.position import PositionSample
from outpost.crypto import load_psk
from outpost.client.tasks.collection import PositionCollectionTask
from outpost.client.tasks.processing import BatchProcessingTask

logging.getLogger("pynmeagps").setLevel(logging.CRITICAL)


class OutpostClient:
    def __init__(
        self,
        device: str,
        baud: int,
        outpost_host: str,
        psk: bytes,
        similarity_threshold: float,
    ):
        self.device = device
        self.baud = baud
        self.outpost_host = outpost_host
        self.psk = psk
        self.similarity_threshold = similarity_threshold
        self.sample_queue: queue.Queue[PositionSample] = queue.Queue()
        self.send_lock = threading.Lock()

        # Task instances
        self.collection_task = PositionCollectionTask(
            device, baud, self.sample_queue, similarity_threshold
        )
        self.processing_task = BatchProcessingTask(
            self.sample_queue, outpost_host, psk, self.send_lock
        )

        self.collection_thread: Thread | None = None
        self.processing_thread: Thread | None = None

    def start(self) -> None:
        # Start tasks
        self.collection_task.start()
        self.processing_task.start()

        # Start collection thread
        self.collection_thread = threading.Thread(
            target=self.collection_task.run, daemon=True
        )
        self.collection_thread.start()

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self.processing_task.run, daemon=True
        )
        self.processing_thread.start()

        logging.info(f"Outpost started on {self.device} at {self.baud} baud")

    def stop(self) -> None:
        # Stop tasks
        self.collection_task.stop()
        self.processing_task.stop()

        # Wait for threads to finish
        if self.collection_thread:
            self.collection_thread.join(timeout=5)

        if self.processing_thread:
            self.processing_thread.join(timeout=5)

        logging.info("Outpost stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Outpost Client")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "--gps",
        "-g",
        default="/dev/ttyGPS0",
        help="Serial device path (default: /dev/ttyGPS0)",
    )
    parser.add_argument(
        "--baud", "-b", type=int, default=38400, help="Baud rate (default: 38400)"
    )
    parser.add_argument(
        "--server",
        "-s",
        help="Outpost server host (e.g., coap://outpost.example.com:5683)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.0001,
        help="Position similarity threshold (default: 0.0001)",
    )
    parser.add_argument(
        "--psk", "-p", help="Path to pre-shared key file for encryption"
    )
    parser.add_argument(
        "--debug", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Load configuration from file if provided (i.e an installation)
    if args.config:
        try:
            with open(args.config, "r") as f:
                config = json.load(f)

            device = config["device"]
            baud = config["baud"]
            server = config["outpost_host"]
            threshold = config["similarity_threshold"]
            psk_path = config["psk_path"]

            logging.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logging.error(f"Failed to load configuration file {args.config}: {e}")
            return
    else:
        # Use command line arguments
        device = args.gps
        baud = args.baud
        server = args.server
        threshold = args.threshold
        psk_path = args.psk

        if not server:
            logging.error("Server host is required (use --server)")
            return

        if not psk_path:
            logging.error("PSK file path is required (use --psk)")
            return

    log_level = logging.INFO if args.debug else logging.WARNING
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        psk = load_psk(psk_path)
        logging.info(f"Loaded PSK from {psk_path}")
    except Exception as e:
        logging.error(f"Failed to load PSK: {e}")
        return

    outpost = OutpostClient(device, baud, server, psk, threshold)

    try:
        outpost.start()

        # Keep the main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        outpost.stop()


if __name__ == "__main__":
    main()

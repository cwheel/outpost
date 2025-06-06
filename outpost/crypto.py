import os
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Encrypted payloads are only valid for this many seconds to prevent endless replay attacks.
# This is a pretty big window, but many of these payloads are send over poor cellular (or satellite)
# connections from remote places, so we want to be as generous as we can be here. Using
# a timestamp prevents us from having to sync counts or track nonces which makes this operation
# more robust on a remote installation. This data isn't critical enough to require a higher
# level of replay protection, if the message was recent then the location was too.
NONCE_VALIDITY_SECONDS = 90

# Width of the nonce in bytes
NONCE_WIDTH = 12


class CryptoError(Exception):
    pass


class InvalidNonceError(CryptoError):
    pass


def load_psk(psk_path: str) -> bytes:
    try:
        with open(psk_path, "rb") as file:
            psk_data = file.read().strip()

        # 32 bytes for AES-256-GCM
        if len(psk_data) != 32:
            raise CryptoError(f"PSK must be exactly 32 bytes, got {len(psk_data)}")

        return psk_data
    except FileNotFoundError:
        raise CryptoError(f"PSK file not found: {psk_path}")
    except Exception as e:
        raise CryptoError(f"Failed to load PSK: {e}")


def generate_timestamp_nonce() -> bytes:
    timestamp = int(time.time())
    random_part = os.urandom(4)
    return timestamp.to_bytes(8, byteorder="big") + random_part


def validate_timestamp_nonce(nonce: bytes) -> None:
    if len(nonce) != NONCE_WIDTH:
        raise InvalidNonceError("Nonce must be 12 bytes")

    timestamp = int.from_bytes(nonce[:8], byteorder="big")
    current_time = int(time.time())

    if abs(current_time - timestamp) > NONCE_VALIDITY_SECONDS:
        raise InvalidNonceError(
            f"Nonce timestamp outside {NONCE_VALIDITY_SECONDS}s window"
        )


def encrypt_payload(payload: bytes, psk: bytes) -> bytes:
    try:
        nonce = generate_timestamp_nonce()
        aesgcm = AESGCM(psk)
        ciphertext = aesgcm.encrypt(nonce, payload, None)

        return nonce + ciphertext
    except Exception as e:
        raise CryptoError(f"Encryption failed: {e}")

    return b""


def decrypt_payload(encrypted_payload: bytes, psk: bytes) -> bytes:
    if len(encrypted_payload) < NONCE_WIDTH + 16:  # AESGCM tag is 16 bytes
        raise CryptoError("Encrypted data too short, failed to decrypt")

    try:
        nonce = encrypted_payload[:NONCE_WIDTH]
        ciphertext = encrypted_payload[NONCE_WIDTH:]

        validate_timestamp_nonce(nonce)

        aesgcm = AESGCM(psk)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext
    except InvalidNonceError:
        raise
    except Exception as e:
        raise CryptoError(f"Decryption failed: {e}")

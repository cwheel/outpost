from abc import abstractmethod
from aiocoap.resource import Resource
from aiocoap import Message
import aiocoap
from typing import Optional

from outpost.crypto import decrypt_payload, encrypt_payload, CryptoError, InvalidNonceError
from outpost.logger import get_logger


logger = get_logger()


class SecureResource(Resource):
    """
    Base class for CoAP resources that automatically handle encryption/decryption
    of message payloads using AES-GCM with timestamp nonces.
    """
    
    def __init__(self, psk: bytes):
        super().__init__()
        self.psk = psk
    
    async def render_get(self, request: Message) -> Message:
        """Handle GET requests with automatic decryption/encryption."""
        try:
            decrypted_payload = None
            if request.payload:
                try:
                    decrypted_payload = decrypt_payload(request.payload, self.psk)
                except (CryptoError, InvalidNonceError) as e:
                    logger.error(f'GET request decryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.UNAUTHORIZED)
            
            # Create new request with decrypted payload
            decrypted_request = Message(
                code=request.code,
                payload=decrypted_payload or b'',
                uri=request.get_request_uri(),
                mtype=request.mtype
            )
            
            response = await self.secure_render_get(decrypted_request)
            
            # Encrypt response payload if present
            if response.payload:
                try:
                    encrypted_payload = encrypt_payload(response.payload, self.psk)
                    response.payload = encrypted_payload
                except CryptoError as e:
                    logger.error(f'GET response encryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
            
            return response
            
        except Exception as e:
            logger.error(f'Error in secure GET handler: {e}')
            return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
    
    async def render_post(self, request: Message) -> Message:
        """Handle POST requests with automatic decryption/encryption."""
        try:
            decrypted_payload = None
            if request.payload:
                try:
                    decrypted_payload = decrypt_payload(request.payload, self.psk)
                except (CryptoError, InvalidNonceError) as e:
                    logger.error(f'POST request decryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.UNAUTHORIZED)
            
            # Create new request with decrypted payload
            decrypted_request = Message(
                code=request.code,
                payload=decrypted_payload or b'',
                uri=request.get_request_uri(),
                mtype=request.mtype
            )
            
            response = await self.secure_render_post(decrypted_request)
            
            # Encrypt response payload if present
            if response.payload:
                try:
                    encrypted_payload = encrypt_payload(response.payload, self.psk)
                    response.payload = encrypted_payload
                except CryptoError as e:
                    logger.error(f'POST response encryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
            
            return response
            
        except Exception as e:
            logger.error(f'Error in secure POST handler: {e}')
            return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
    
    async def render_put(self, request: Message) -> Message:
        """Handle PUT requests with automatic decryption/encryption."""
        try:
            decrypted_payload = None
            if request.payload:
                try:
                    decrypted_payload = decrypt_payload(request.payload, self.psk)
                except (CryptoError, InvalidNonceError) as e:
                    logger.error(f'PUT request decryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.UNAUTHORIZED)
            
            # Create new request with decrypted payload
            decrypted_request = Message(
                code=request.code,
                payload=decrypted_payload or b'',
                uri=request.get_request_uri(),
                mtype=request.mtype
            )
            
            response = await self.secure_render_put(decrypted_request)
            
            # Encrypt response payload if present
            if response.payload:
                try:
                    encrypted_payload = encrypt_payload(response.payload, self.psk)
                    response.payload = encrypted_payload
                except CryptoError as e:
                    logger.error(f'PUT response encryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
            
            return response
            
        except Exception as e:
            logger.error(f'Error in secure PUT handler: {e}')
            return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
    
    async def render_delete(self, request: Message) -> Message:
        """Handle DELETE requests with automatic decryption/encryption."""
        try:
            decrypted_payload = None
            if request.payload:
                try:
                    decrypted_payload = decrypt_payload(request.payload, self.psk)
                except (CryptoError, InvalidNonceError) as e:
                    logger.error(f'DELETE request decryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.UNAUTHORIZED)
            
            # Create new request with decrypted payload
            decrypted_request = Message(
                code=request.code,
                payload=decrypted_payload or b'',
                uri=request.get_request_uri(),
                mtype=request.mtype
            )
            
            response = await self.secure_render_delete(decrypted_request)
            
            # Encrypt response payload if present
            if response.payload:
                try:
                    encrypted_payload = encrypt_payload(response.payload, self.psk)
                    response.payload = encrypted_payload
                except CryptoError as e:
                    logger.error(f'DELETE response encryption failed: {e}')
                    return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
            
            return response
            
        except Exception as e:
            logger.error(f'Error in secure DELETE handler: {e}')
            return Message(mtype=aiocoap.NON, code=aiocoap.INTERNAL_SERVER_ERROR)
    
    # Abstract methods for subclasses to implement
    async def secure_render_get(self, request: Message) -> Message:
        """Override this method to handle decrypted GET requests."""
        return Message(mtype=aiocoap.NON, code=aiocoap.METHOD_NOT_ALLOWED)
    
    async def secure_render_post(self, request: Message) -> Message:
        """Override this method to handle decrypted POST requests."""
        return Message(mtype=aiocoap.NON, code=aiocoap.METHOD_NOT_ALLOWED)
    
    async def secure_render_put(self, request: Message) -> Message:
        """Override this method to handle decrypted PUT requests."""
        return Message(mtype=aiocoap.NON, code=aiocoap.METHOD_NOT_ALLOWED)
    
    async def secure_render_delete(self, request: Message) -> Message:
        """Override this method to handle decrypted DELETE requests."""
        return Message(mtype=aiocoap.NON, code=aiocoap.METHOD_NOT_ALLOWED)
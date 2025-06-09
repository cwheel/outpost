import os
import pytest

# Set DEBUG=1 globally for all tests to avoid file logging permission issues
os.environ["DEBUG"] = "1"

@pytest.fixture
def test_psk():
    return b"test_psk_key_123"
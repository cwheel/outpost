#!/bin/bash

# Generate PSK for Outpost client/server encryption
# Creates a 32-byte (256-bit) random key suitable for AES-256-GCM

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <output_filename>"
    echo "Example: $0 outpost.psk"
    exit 1
fi

OUTPUT_FILE="$1"

echo "Generating 32-byte PSK for Outpost..."

# Generate 32 random bytes
openssl rand 32 > "$OUTPUT_FILE"
echo "PSK written to: $OUTPUT_FILE"

echo ""
echo "PSK file generated successfully!"
echo "Keep this file secure and distribute to both client and server."
echo ""
echo "Usage:"
echo "  Server: OUTPOST_PSK=$OUTPUT_FILE python -m outpost.serve"
echo "  Client: python -m outpost.client --psk $OUTPUT_FILE"
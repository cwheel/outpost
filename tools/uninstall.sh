#!/bin/bash

# VenusOS Outpost Client Uninstaller
# This script removes the Outpost client and cleans up all installed files

set -e

INSTALL_DIR="/etc/outpost"
SERVICE_NAME="outpost-client"

usage() {
    echo "Usage: $0 [--keep-deps]"
    echo ""
    echo "Options:"
    echo "  --keep-deps          Keep Python dependencies installed"
    echo "  --help              Show this help message"
    exit 1
}

# Parse command line arguments
KEEP_DEPS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-deps)
            KEEP_DEPS=true
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "Uninstalling Outpost client..."

# Check if we're running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root"
    exit 1
fi

# Stop and disable the service
echo "Stopping and disabling service..."
if [[ -f "/etc/init.d/$SERVICE_NAME" ]]; then
    if /etc/init.d/"$SERVICE_NAME" status >/dev/null 2>&1; then
        /etc/init.d/"$SERVICE_NAME" stop
        echo "Service stopped"
    fi
    
    # Disable service from startup
    update-rc.d "$SERVICE_NAME" remove 2>/dev/null || true
    echo "Service disabled"
    
    # Remove init.d service file
    echo "Removing init.d service file..."
    rm -f "/etc/init.d/$SERVICE_NAME"
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    echo "Removing installation directory: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
fi

# Optionally remove Python dependencies
if [[ "$KEEP_DEPS" = false ]]; then
    echo "Removing Python dependencies..."
    pip3 uninstall -y aiocoap pynmeagps pyserial asyncpg cryptography 2>/dev/null || true
else
    echo "Keeping Python dependencies (--keep-deps specified)"
fi

echo ""
echo "Uninstallation complete!"
echo "The system has been restored to its original state."

# Verify cleanup
if [[ ! -d "$INSTALL_DIR" ]] && [[ ! -f "/etc/init.d/$SERVICE_NAME" ]]; then
    echo "✓ All files successfully removed"
else
    echo "⚠ Some files may still remain:"
    [[ -d "$INSTALL_DIR" ]] && echo "  - $INSTALL_DIR still exists"
    [[ -f "/etc/init.d/$SERVICE_NAME" ]] && echo "  - Service file still exists"
fi
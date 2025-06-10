#!/bin/bash

# VenusOS Outpost Client Installer
# This script installs the Outpost client and configures it to run as a service

set -e

INSTALL_DIR="/etc/outpost"
SERVICE_NAME="outpost-client"
PYTHON_PATH="/usr/bin/python3"
REPO_DIR="$(dirname "$(dirname "$(realpath "$0")")")"

usage() {
    echo "Usage: $0 [--psk-file <path_to_psk_file>] [--host <server_host>] [--device <gps_device>] [--baud <baud_rate>]"
    echo ""
    echo "For new installations:"
    echo "  --psk-file <file>     Path to PSK file (required for new installs)"
    echo "  --host <host>         Outpost server host (default: outpost.local:5683)"
    echo "  --device <device>     GPS device path (default: /dev/ttyUSB0)"
    echo "  --baud <rate>         GPS baud rate (default: 9600)"
    echo ""
    echo "For updates:"
    echo "  Run without arguments to update code on existing installation"
    echo ""
    echo "Options:"
    echo "  --help               Show this help message"
    exit 1
}

# Parse command line arguments
PSK_FILE=""
HOST="outpost.local:5683"
DEVICE="/dev/ttyUSB0"
BAUD="9600"

while [[ $# -gt 0 ]]; do
    case $1 in
        --psk-file)
            PSK_FILE="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --baud)
            BAUD="$2"
            shift 2
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

# Check if this is an existing installation
IS_UPDATE=false
if [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/config.json" ]]; then
    IS_UPDATE=true
    echo "Existing installation detected - performing code update"
fi

# Validate arguments based on install type
if [[ "$IS_UPDATE" = false ]]; then
    if [[ -z "$PSK_FILE" ]]; then
        echo "Error: --psk-file is required for new installations"
        usage
    fi
    
    if [[ ! -f "$PSK_FILE" ]]; then
        echo "Error: PSK file '$PSK_FILE' not found"
        exit 1
    fi
    
    echo "Installing Outpost client..."
else
    # For updates, load existing configuration
    if [[ -f "$INSTALL_DIR/config.json" ]]; then
        echo "Loading existing configuration..."
        EXISTING_DEVICE=$(python3 -c "import json; print(json.load(open('$INSTALL_DIR/config.json'))['device'])")
        EXISTING_BAUD=$(python3 -c "import json; print(json.load(open('$INSTALL_DIR/config.json'))['baud'])")
        EXISTING_HOST=$(python3 -c "import json; print(json.load(open('$INSTALL_DIR/config.json'))['outpost_host'])")
        
        # Use existing values if not specified on command line
        [[ "$DEVICE" == "/dev/ttyUSB0" ]] && DEVICE="$EXISTING_DEVICE"
        [[ "$BAUD" == "9600" ]] && BAUD="$EXISTING_BAUD"
        [[ "$HOST" == "outpost.local:5683" ]] && HOST="$EXISTING_HOST"
        
        echo "Updating Outpost client..."
    fi
fi

# Check if we're running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root"
    exit 1
fi

# Stop service if running (for updates)
if [[ "$IS_UPDATE" = true ]] && systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping service for update..."
    systemctl stop "$SERVICE_NAME"
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy source code
echo "Copying source code..."
cp -r "$REPO_DIR/outpost" "$INSTALL_DIR/"

# Handle PSK file
if [[ "$IS_UPDATE" = false ]]; then
    # New installation - copy PSK file
    echo "Installing PSK file..."
    cp "$PSK_FILE" "$INSTALL_DIR/outpost.psk"
    chmod 600 "$INSTALL_DIR/outpost.psk"
else
    # Update - keep existing PSK file
    echo "Preserving existing PSK file..."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install aiocoap pynmeagps pyserial asyncpg cryptography

# Create or update configuration file
if [[ "$IS_UPDATE" = false ]]; then
    echo "Creating configuration file..."
    cat > "$INSTALL_DIR/config.json" << EOF
{
    "device": "$DEVICE",
    "baud": $BAUD,
    "outpost_host": "$HOST",
    "psk_path": "$INSTALL_DIR/outpost.psk",
    "similarity_threshold": 0.0001
}
EOF
else
    echo "Updating configuration file..."
    # Update config with potentially new values while preserving others
    python3 -c "
import json
with open('$INSTALL_DIR/config.json', 'r') as f:
    config = json.load(f)
config['device'] = '$DEVICE'
config['baud'] = $BAUD
config['outpost_host'] = '$HOST'
with open('$INSTALL_DIR/config.json', 'w') as f:
    json.dump(config, f, indent=4)
"
fi

# Create startup script
echo "Creating startup script..."
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash

# Wait for GPS device to be available
GPS_DEVICE=$(python3 -c "import json; print(json.load(open('/etc/outpost/config.json'))['device'])")
HOST_CHECK=$(python3 -c "import json; print(json.load(open('/etc/outpost/config.json'))['outpost_host'])" | cut -d: -f1)

echo "Waiting for GPS device $GPS_DEVICE..."
for i in {1..30}; do
    if [[ -e "$GPS_DEVICE" ]]; then
        echo "GPS device found"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "GPS device not found after 30 seconds, continuing anyway..."
    fi
    sleep 1
done

echo "Checking network connectivity to $HOST_CHECK..."
for i in {1..60}; do
    if ping -c 1 "$HOST_CHECK" >/dev/null 2>&1; then
        echo "Network connectivity confirmed"
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "Network not available after 60 seconds, continuing anyway..."
    fi
    sleep 1
done

echo "Starting Outpost client..."
cd /etc/outpost
export PYTHONPATH="/etc/outpost:$PYTHONPATH"
exec /usr/bin/python3 -m outpost.client --config config.json
EOF

chmod +x "$INSTALL_DIR/start.sh"

# Create systemd service file
echo "Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Outpost GPS Client
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/start.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
if [[ "$IS_UPDATE" = false ]]; then
    echo "Enabling and starting service..."
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    
    echo ""
    echo "Installation complete!"
else
    echo "Restarting service..."
    systemctl daemon-reload
    systemctl start "$SERVICE_NAME"
    
    echo ""
    echo "Update complete!"
fi

echo "Service status:"
systemctl status "$SERVICE_NAME" --no-pager -l
echo ""
echo "To view logs: journalctl -u $SERVICE_NAME -f"
echo "To restart: systemctl restart $SERVICE_NAME"
echo "To stop: systemctl stop $SERVICE_NAME"
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
if [[ "$IS_UPDATE" = true ]] && [[ -f "/etc/init.d/$SERVICE_NAME" ]]; then
    if /etc/init.d/"$SERVICE_NAME" status >/dev/null 2>&1; then
        echo "Stopping service for update..."
        /etc/init.d/"$SERVICE_NAME" stop
    fi
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
pip3 install aiocoap pynmeagps pyserial cryptography

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

# Create init.d service script
echo "Creating init.d service script..."
cat > "/etc/init.d/$SERVICE_NAME" << 'EOF'
#!/bin/bash
### BEGIN INIT INFO
# Provides:          outpost-client
# Required-Start:    $network $remote_fs $syslog
# Required-Stop:     $network $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Outpost GPS Client
# Description:       GPS position tracking client for Outpost server
### END INIT INFO

DAEMON="outpost-client"
DAEMON_USER="root"
DAEMON_PATH="/etc/outpost"
DAEMON_SCRIPT="$DAEMON_PATH/start.sh"
LOCK_FILE="/var/lock/subsys/$DAEMON"
PID_FILE="/var/run/$DAEMON.pid"

start() {
    echo -n "Starting $DAEMON: "
    if [[ -f $PID_FILE ]] && kill -0 $(cat $PID_FILE) 2>/dev/null; then
        echo "already running"
        return 1
    fi
    
    cd "$DAEMON_PATH"
    nohup "$DAEMON_SCRIPT" > /var/log/$DAEMON.log 2>&1 &
    echo $! > "$PID_FILE"
    
    if [[ $? -eq 0 ]]; then
        touch "$LOCK_FILE"
        echo "started"
        return 0
    else
        echo "failed"
        return 1
    fi
}

stop() {
    echo -n "Stopping $DAEMON: "
    if [[ ! -f $PID_FILE ]]; then
        echo "not running"
        return 1
    fi
    
    PID=$(cat $PID_FILE)
    if kill -TERM $PID 2>/dev/null; then
        # Wait for process to terminate
        for i in {1..10}; do
            if ! kill -0 $PID 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if kill -0 $PID 2>/dev/null; then
            kill -KILL $PID 2>/dev/null
        fi
        
        rm -f "$PID_FILE" "$LOCK_FILE"
        echo "stopped"
        return 0
    else
        echo "failed"
        return 1
    fi
}

status() {
    if [[ -f $PID_FILE ]] && kill -0 $(cat $PID_FILE) 2>/dev/null; then
        echo "$DAEMON is running (PID $(cat $PID_FILE))"
        return 0
    else
        echo "$DAEMON is not running"
        return 1
    fi
}

restart() {
    stop
    sleep 2
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart|reload)
        restart
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac

exit $?
EOF

chmod +x "/etc/init.d/$SERVICE_NAME"

# Enable and start the service
if [[ "$IS_UPDATE" = false ]]; then
    echo "Enabling and starting service..."
    update-rc.d "$SERVICE_NAME" defaults
    /etc/init.d/"$SERVICE_NAME" start
    
    echo ""
    echo "Installation complete!"
else
    echo "Restarting service..."
    /etc/init.d/"$SERVICE_NAME" restart
    
    echo ""
    echo "Update complete!"
fi

echo "Service status:"
/etc/init.d/"$SERVICE_NAME" status
echo ""
echo "To view logs: tail -f /var/log/$SERVICE_NAME.log"
echo "To restart: /etc/init.d/$SERVICE_NAME restart"
echo "To stop: /etc/init.d/$SERVICE_NAME stop"
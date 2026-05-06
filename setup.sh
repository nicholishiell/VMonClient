#!/bin/bash
# Deploy VM usage monitor services and configuration
# Run as root or with sudo

set -e  # exit on error
set -u  # treat unset vars as errors

# ----------------------------
# Configuration
# ----------------------------
SERVICE_DIR="/etc/systemd/system"
BIN_DIR="/usr/local/lib/vm_monitor"
CONFIG_DIR="/etc/vm_monitor"
DATA_DIR="/var/lib/vm_monitor"
LOG_DIR="/var/log/vm_monitor"

API_SERVICE="vm-monitor-api.service"
CLIENT_SERVICE="vm-monitor-client.service"
CONFIG_FILE="config.yaml"
SCRIPTS=("vm_monitor/vm_monitor_api.py" "vm_monitor/vm_monitor_client.py" "vm_monitor/vm_monitor_db.py")

# ----------------------------
# Create vmmonitor user
# ----------------------------
if id "vmmonitor" &>/dev/null; then
    echo "User 'vmmonitor' already exists."
else
    echo "Creating user 'vmmonitor'..."
    sudo useradd -r -s /usr/sbin/nologin vmmonitor
fi

# ----------------------------
# Create directories
# ----------------------------

echo "Creating directories..."
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

# ----------------------------
# Copy scripts
# ----------------------------
echo "Copying Python scripts..."
for script in "${SCRIPTS[@]}"; do
    if [[ -f "$script" ]]; then
        cp "$script" "$BIN_DIR/"
    else
        echo "Warning: $script not found!"
    fi
done

cp requirements.txt "$BIN_DIR/"

echo "Installing Python dependencies..."
python -m venv "$BIN_DIR/venv"
source "$BIN_DIR/venv/bin/activate"
pip install -r "$BIN_DIR/requirements.txt"
deactivate

# ----------------------------
# Copy config file
# ----------------------------
echo "Copying config file..."
if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "$CONFIG_DIR/"
else
    echo "Warning: $CONFIG_FILE not found!"
fi

# ----------------------------
# Copy systemd service files
# ----------------------------
echo "Installing systemd service files..."
if [[ -f "$API_SERVICE" ]]; then
    cp "$API_SERVICE" "$SERVICE_DIR/"
else
    echo "Warning: $API_SERVICE not found!"
fi

if [[ -f "$CLIENT_SERVICE" ]]; then
    cp "$CLIENT_SERVICE" "$SERVICE_DIR/"
else
    echo "Warning: $CLIENT_SERVICE not found!"
fi

# ----------------------------
# Permissions
# ----------------------------
echo "Setting permissions..."
# chmod 755 "$BIN_DIR"/*.py
# chmod 644 "$CONFIG_DIR"/*.yaml
# chmod 644 "$SERVICE_DIR"/vm-monitor-*.service
# chown root:root "$CONFIG_DIR"/*.yaml "$SERVICE_DIR"/vm-monitor-*.service

sudo chown -R vmmonitor:vmmonitor "$BIN_DIR"
sudo chown -R vmmonitor:vmmonitor "$DATA_DIR"
sudo chown -R vmmonitor:vmmonitor "$CONFIG_DIR"

# ----------------------------
# Reload systemd and enable services
# ----------------------------
echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling services..."
systemctl enable vm-monitor-client.service
systemctl enable vm-monitor-api.service

echo "Starting services..."
systemctl start vm-monitor-client.service
systemctl start vm-monitor-api.service

echo "✅ Deployment complete!"
echo "Scripts installed to: $BIN_DIR"
echo "Config stored in:     $CONFIG_DIR"
echo "Database will live in: $DATA_DIR"
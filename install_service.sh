#!/bin/bash

# Exit on error
set -e

# Check if running as root/sudo
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run with sudo: sudo ./install_service.sh"
   exit 1
fi

APP_DIR=$(pwd)
SERVICE_NAME="ai-match"
USER_NAME=$(logname || echo $USER)

echo "--- Installing $SERVICE_NAME Service ---"
echo "App Directory: $APP_DIR"
echo "Running as User: $USER_NAME"

# Create the systemd service file
cat <<EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Everystore AI Product Match Microservice
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Always restart on crash
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start
echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling $SERVICE_NAME (to start on boot)..."
systemctl enable $SERVICE_NAME

echo "Starting $SERVICE_NAME..."
systemctl start $SERVICE_NAME

echo "--- Service Installed and Started ---"
echo "Check status: sudo systemctl status $SERVICE_NAME"
echo "View logs: sudo journalctl -u $SERVICE_NAME -f"

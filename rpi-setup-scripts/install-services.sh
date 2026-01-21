#!/bin/bash
# Setup script to install button listener and client mode services

set -e

echo "Installing button listener and WiFi client mode services..."

# Copy service files to systemd directory
echo "Installing service files..."
sudo cp "$(dirname "$0")/button-listener.service" /etc/systemd/system/
sudo cp "$(dirname "$0")/switch-to-client.service" /etc/systemd/system/

# Copy scripts to /home/pi if they're not already there
echo "Installing scripts..."
sudo cp "$(dirname "$0")/../mode-btn/button_listener.py" /usr/local/bin
sudo cp "$(dirname "$0)/../rpi-wifi-provisioner/scripts/switch-to-client.sh" /usr/local/bin

# Make scripts executable
sudo chmod +x /usr/local/bin/button_listener.py
sudo chmod +x /usr/local/bin/switch-to-client.sh

# Reload systemd daemon
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable services to start on boot
echo "Enabling services..."
sudo systemctl enable button-listener.service
sudo systemctl enable switch-to-client.service

# Start services immediately
echo "Starting services..."
sudo systemctl start switch-to-client.service
sudo systemctl start button-listener.service

echo ""
echo "✓ Services installed and started successfully!"
echo ""
echo "To check status:"
echo "  sudo systemctl status button-listener.service"
echo "  sudo systemctl status switch-to-client.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u button-listener.service -f"
echo "  sudo journalctl -u switch-to-client.service -f"
echo ""

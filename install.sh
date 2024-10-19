#!/bin/bash

set -e

echo "Installing Network Monitor..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Install required system packages
sudo apt-get update
sudo apt-get install -y python3-pip influxdb grafana speedtest-cli

# Install Python dependencies
pip3 install influxdb requests

# Download the network_monitor.py script
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/network_monitor.py

# Make the script executable
chmod +x network_monitor.py

# Move the script to a suitable location
sudo mv network_monitor.py /usr/local/bin/network-monitor

# Start and enable InfluxDB and Grafana services
sudo systemctl start influxdb
sudo systemctl enable influxdb
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

echo "Installation complete!"
echo "To configure the Network Monitor, run: network-monitor --configure"
echo "To start monitoring, run: network-monitor --start"

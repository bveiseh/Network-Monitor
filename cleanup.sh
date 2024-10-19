#!/bin/bash

set -e

# Color codes for output styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}[+] $1${NC}"
}

# Function to print error messages and exit
print_error() {
    echo -e "${RED}[!] Error: $1${NC}"
    exit 1
}

print_status "Starting cleanup of Network Monitor..."

# Stop and disable services
print_status "Stopping and disabling services..."
sudo systemctl stop network-monitor.service || true
sudo systemctl disable network-monitor.service || true
sudo systemctl stop influxdb || true
sudo systemctl disable influxdb || true
sudo systemctl stop grafana-server || true
sudo systemctl disable grafana-server || true

# Remove installed packages
print_status "Removing installed packages..."
sudo apt-get remove -y python3-pip influxdb grafana speedtest-cli || true
sudo apt-get autoremove -y

# Remove Python dependencies
print_status "Removing Python dependencies..."
pip3 uninstall -y influxdb requests || true

# Remove configuration files and scripts
print_status "Removing configuration files and scripts..."
sudo rm -f /etc/network_monitor_config.json
sudo rm -f /usr/local/bin/network-monitor
sudo rm -f /etc/systemd/system/network-monitor.service

# Remove cloned repository
print_status "Removing cloned repository..."
sudo rm -rf ~/Network-Monitor

# Clean up InfluxDB and Grafana data
print_status "Cleaning up InfluxDB and Grafana data..."
sudo rm -rf /var/lib/influxdb
sudo rm -rf /var/lib/grafana

# Reload systemd
sudo systemctl daemon-reload

print_success "Cleanup completed successfully!"
print_status "Note: Some components may require manual removal if they were installed differently."
print_status "You may need to reboot your system to complete the cleanup process."

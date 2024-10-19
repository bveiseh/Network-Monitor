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

# Pre-flight checks
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run as root or with sudo"
    fi

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3 and try again."
    fi

    # Check if ports are available
    if lsof -Pi :8086 -sTCP:LISTEN -t >/dev/null ; then
        print_error "Port 8086 is already in use. Please free up this port or modify the InfluxDB configuration."
    fi

    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null ; then
        print_error "Port 3000 is already in use. Please free up this port or modify the Grafana configuration."
    fi

    print_success "All system requirements met."
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check if services are running
    if systemctl is-active --quiet influxdb; then
        print_success "InfluxDB service is running."
    else
        print_error "InfluxDB service is not running. Please check the logs."
    fi

    if systemctl is-active --quiet grafana-server; then
        print_success "Grafana service is running."
    else
        print_error "Grafana service is not running. Please check the logs."
    fi

    if systemctl is-active --quiet network-monitor; then
        print_success "Network monitor service is running."
    else
        print_error "Network monitor service is not running. Please check the logs."
    fi

    print_success "All services are running. Installation verified."
}

print_status "Starting installation of Enhanced Network Monitor (Bash version)..."

# Run pre-flight checks
check_requirements

# Install required packages
print_status "Installing required packages..."
apt-get update
apt-get install -y python3 python3-pip python3-venv influxdb grafana speedtest-cli curl jq

# Create project directory
mkdir -p /opt/network-monitor
cd /opt/network-monitor

# Download necessary files
print_status "Downloading project files..."
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/network_monitor.py
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/requirements.txt
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/netdash.json

# Set up Python virtual environment
print_status "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Configure Network Monitor
print_status "Configuring Network Monitor..."
python3 network_monitor.py --configure

# Start InfluxDB and Grafana services
print_status "Starting InfluxDB and Grafana services..."
systemctl start influxdb
systemctl start grafana-server
systemctl enable influxdb
systemctl enable grafana-server

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Configure Grafana
print_status "Configuring Grafana..."
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"

# Create Grafana API key
API_KEY_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d '{"name":"NetworkMonitorKey", "role": "Admin"}' ${GRAFANA_URL}/api/auth/keys -u ${GRAFANA_USER}:${GRAFANA_PASSWORD})
GRAFANA_API_KEY=$(echo $API_KEY_RESPONSE | jq -r '.key')

if [ -z "$GRAFANA_API_KEY" ] || [ "$GRAFANA_API_KEY" == "null" ]; then
    print_error "Failed to generate Grafana API key automatically. Please check Grafana logs and try again."
fi

# Create InfluxDB data source
curl -X POST -H "Content-Type: application/json" -d '{
    "name":"InfluxDB",
    "type":"influxdb",
    "url":"http://localhost:8086",
    "access":"proxy",
    "database":"network_metrics"
}' ${GRAFANA_URL}/api/datasources -H "Authorization: Bearer ${GRAFANA_API_KEY}"

# Import Grafana dashboard
DASHBOARD_ID=$(curl -X POST -H "Content-Type: application/json" -d @netdash.json ${GRAFANA_URL}/api/dashboards/db -H "Authorization: Bearer ${GRAFANA_API_KEY}" | jq -r '.id')

# Update the network_monitor.py file with the Grafana API key
sed -i "s/GRAFANA_API_KEY = '.*'/GRAFANA_API_KEY = '${GRAFANA_API_KEY}'/" network_monitor.py

# Create systemd service file
print_status "Creating systemd service..."
cat << EOF > /etc/systemd/system/network-monitor.service
[Unit]
Description=Enhanced Network Monitor
After=network.target influxdb.service grafana-server.service

[Service]
ExecStart=/opt/network-monitor/venv/bin/python /opt/network-monitor/network_monitor.py
WorkingDirectory=/opt/network-monitor
User=root
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start the service
systemctl daemon-reload
systemctl enable network-monitor
systemctl start network-monitor

# Verify installation
verify_installation

print_success "Installation completed successfully!"
echo -e "${GREEN}You can access Grafana at http://localhost:3000 (default credentials: admin/admin)${NC}"
echo -e "${YELLOW}Please change the default password after your first login.${NC}"
echo -e "${YELLOW}Imported dashboard ID: ${DASHBOARD_ID}${NC}"
echo -e "${YELLOW}Grafana API Key: ${GRAFANA_API_KEY}${NC}"
echo -e "${YELLOW}The Network Monitor service is now running. You can check its status with: systemctl status network-monitor${NC}"

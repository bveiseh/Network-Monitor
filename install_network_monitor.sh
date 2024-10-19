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

# Function to check if a command was successful
check_command() {
    if [ $? -ne 0 ]; then
        print_error "$1"
    fi
}

print_status "Starting installation of Enhanced Network Monitor..."

# Detect OS and set variables accordingly
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -si)
    VER=$(lsb_release -sr)
else
    OS=$(uname -s)
    VER=$(uname -r)
fi

print_status "Detected OS: $OS $VER"

# Update system and install basic requirements
if [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian GNU/Linux" ]]; then
    print_status "Updating system and installing basic requirements..."
    sudo apt-get update && sudo apt-get upgrade -y
    check_command "Failed to update system"
    sudo apt-get install -y python3 python3-pip curl wget gnupg2 apt-transport-https software-properties-common lsb-release jq
    check_command "Failed to install basic requirements"
elif [[ "$OS" == "CentOS Linux" ]] || [[ "$OS" == "Red Hat Enterprise Linux" ]]; then
    print_status "Updating system and installing basic requirements..."
    sudo yum update -y
    check_command "Failed to update system"
    sudo yum install -y python3 python3-pip curl wget gnupg2 yum-utils epel-release jq
    check_command "Failed to install basic requirements"
else
    print_error "Unsupported OS: $OS"
fi

# Verify Python and pip installation
print_status "Verifying Python and pip installation..."
python3 --version || print_error "Python3 is not installed correctly"
pip3 --version || print_error "pip3 is not installed correctly"

# Install InfluxDB
print_status "Installing InfluxDB..."
INFLUXDB_VERSION="1.8.10"
if [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian GNU/Linux" ]]; then
    wget -qO- https://repos.influxdata.com/influxdb.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/influxdb.gpg > /dev/null
    check_command "Failed to add InfluxDB GPG key"
    echo "deb [signed-by=/etc/apt/trusted.gpg.d/influxdb.gpg] https://repos.influxdata.com/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
    check_command "Failed to add InfluxDB repository"
    sudo apt-get update
    check_command "Failed to update package lists after adding InfluxDB repository"
    sudo apt-get install -y influxdb=$INFLUXDB_VERSION
    check_command "Failed to install InfluxDB"
elif [[ "$OS" == "CentOS Linux" ]] || [[ "$OS" == "Red Hat Enterprise Linux" ]]; then
    sudo yum install -y https://dl.influxdata.com/influxdb/releases/influxdb-$INFLUXDB_VERSION.x86_64.rpm
    check_command "Failed to install InfluxDB"
fi

# Install Grafana
print_status "Installing Grafana..."
GRAFANA_VERSION="9.5.2"
if [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian GNU/Linux" ]]; then
    wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
    check_command "Failed to add Grafana GPG key"
    echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
    check_command "Failed to add Grafana repository"
    sudo apt-get update
    check_command "Failed to update package lists after adding Grafana repository"
    sudo apt-get install -y grafana=$GRAFANA_VERSION
    check_command "Failed to install Grafana"
elif [[ "$OS" == "CentOS Linux" ]] || [[ "$OS" == "Red Hat Enterprise Linux" ]]; then
    sudo yum install -y https://dl.grafana.com/oss/release/grafana-$GRAFANA_VERSION-1.x86_64.rpm
    check_command "Failed to install Grafana"
fi

# Install Ookla Speedtest CLI
print_status "Installing Ookla Speedtest CLI..."
if [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian GNU/Linux" ]]; then
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
    check_command "Failed to add Ookla Speedtest CLI repository"
    sudo apt-get install -y speedtest
    check_command "Failed to install Ookla Speedtest CLI"
elif [[ "$OS" == "CentOS Linux" ]] || [[ "$OS" == "Red Hat Enterprise Linux" ]]; then
    sudo yum install -y https://packagecloud.io/ookla/speedtest-cli/packages/el/7/speedtest-1.2.0-1.x86_64.rpm/download
    check_command "Failed to install Ookla Speedtest CLI"
fi

# Install required Python packages
print_status "Installing required Python packages..."
sudo pip3 install influxdb==5.3.1 requests==2.28.2
check_command "Failed to install Python packages"

# Create InfluxDB database
print_status "Creating InfluxDB database..."
sudo systemctl start influxdb
sudo systemctl enable influxdb
sleep 5  # Wait for InfluxDB to start
influx -execute "CREATE DATABASE network_metrics"
check_command "Failed to create InfluxDB database"

# Set up the network monitor service
print_status "Setting up network monitor service..."
sudo tee /etc/systemd/system/network-monitor.service > /dev/null << EOL
[Unit]
Description=Enhanced Network Monitor
After=network.target influxdb.service grafana-server.service

[Service]
ExecStart=/usr/bin/python3 /opt/network-monitor/network_monitor.py
Restart=always
User=root
WorkingDirectory=/opt/network-monitor

[Install]
WantedBy=multi-user.target
EOL
check_command "Failed to create network monitor service"

# Create directory for the application
print_status "Creating application directory..."
sudo mkdir -p /opt/network-monitor
sudo chown $USER:$USER /opt/network-monitor
check_command "Failed to create application directory"

# Download the network_monitor.py script
print_status "Downloading network_monitor.py..."
curl -o /opt/network-monitor/network_monitor.py https://raw.githubusercontent.com/yourusername/network-monitor/main/network_monitor.py
check_command "Failed to download network_monitor.py"

# Reload systemd and enable services
print_status "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable influxdb.service
sudo systemctl enable grafana-server.service
sudo systemctl enable network-monitor.service

sudo systemctl start influxdb.service
sudo systemctl start grafana-server.service
sudo systemctl start network-monitor.service
check_command "Failed to start services"

# Configure Grafana
print_status "Configuring Grafana..."
sleep 10  # Wait for Grafana to start

# Set up Grafana datasource
curl -X POST -H "Content-Type: application/json" -d '{
    "name":"InfluxDB",
    "type":"influxdb",
    "url":"http://localhost:8086",
    "access":"proxy",
    "database":"network_metrics"
}' http://admin:admin@localhost:3000/api/datasources
check_command "Failed to set up Grafana datasource"

# Import Grafana dashboard
DASHBOARD_ID=$(curl -X POST -H "Content-Type: application/json" -d '{
    "dashboard": {
        "id": null,
        "title": "Network Monitor Dashboard",
        "tags": [ "network", "monitoring" ],
        "timezone": "browser",
        "schemaVersion": 16,
        "version": 0
    },
    "folderId": 0,
    "overwrite": false
}' http://admin:admin@localhost:3000/api/dashboards/db | jq -r '.id')

check_command "Failed to import Grafana dashboard"

print_success "Grafana dashboard created with ID: $DASHBOARD_ID"

print_success "Installation completed successfully!"
echo -e "${GREEN}You can access Grafana at http://localhost:3000 (default credentials: admin/admin)${NC}"
echo -e "${YELLOW}Please change the default password after your first login.${NC}"

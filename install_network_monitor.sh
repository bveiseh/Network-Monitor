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
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker and try again."
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
    fi

    # Check if ports are available
    if lsof -Pi :9834 -sTCP:LISTEN -t >/dev/null ; then
        print_error "Port 9834 is already in use. Please free up this port or modify the docker-compose.yml file."
    fi

    print_success "All system requirements met."
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check if containers are running
    if [ "$(docker ps -q -f name=network-monitor)" ]; then
        print_success "Network monitor container is running."
    else
        print_error "Network monitor container is not running. Please check the logs."
    fi

    if [ "$(docker ps -q -f name=influxdb)" ]; then
        print_success "InfluxDB container is running."
    else
        print_error "InfluxDB container is not running. Please check the logs."
    fi

    if [ "$(docker ps -q -f name=grafana)" ]; then
        print_success "Grafana container is running."
    else
        print_error "Grafana container is not running. Please check the logs."
    fi

    print_success "All containers are running. Installation verified."
}

print_status "Starting installation of Enhanced Network Monitor..."

# Run pre-flight checks
check_requirements

# Create project directory
mkdir -p network-monitor
cd network-monitor

# Download necessary files
print_status "Downloading project files..."
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/Dockerfile
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/network_monitor.py
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/requirements.txt
curl -O https://raw.githubusercontent.com/bveiseh/Network-Monitor/main/netdash.json

# Run the Python script in configuration mode
print_status "Configuring Network Monitor..."
python3 network_monitor.py --configure

# Start the containers
print_status "Starting Docker containers..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Configure Grafana
print_status "Configuring Grafana..."
GRAFANA_URL="http://localhost:9834"
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
    "url":"http://influxdb:8086",
    "access":"proxy",
    "database":"network_metrics"
}' ${GRAFANA_URL}/api/datasources -H "Authorization: Bearer ${GRAFANA_API_KEY}"

# Import Grafana dashboard
DASHBOARD_ID=$(curl -X POST -H "Content-Type: application/json" -d @netdash.json ${GRAFANA_URL}/api/dashboards/db -H "Authorization: Bearer ${GRAFANA_API_KEY}" | jq -r '.id')

# Update the network_monitor.py file with the Grafana API key
sed -i "s/GRAFANA_API_KEY = '.*'/GRAFANA_API_KEY = '${GRAFANA_API_KEY}'/" network_monitor.py

# Verify installation
verify_installation

print_success "Installation completed successfully!"
echo -e "${GREEN}You can access Grafana at http://localhost:9834 (default credentials: admin/admin)${NC}"
echo -e "${YELLOW}Please change the default password after your first login.${NC}"
echo -e "${YELLOW}Imported dashboard ID: ${DASHBOARD_ID}${NC}"
echo -e "${YELLOW}Grafana API Key: ${GRAFANA_API_KEY}${NC}"

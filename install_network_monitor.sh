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

print_status "Starting installation of Enhanced Network Monitor..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker and try again."
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose and try again."
fi

# Create project directory
mkdir -p network-monitor
cd network-monitor

# Download necessary files
print_status "Downloading project files..."
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/Dockerfile
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/network_monitor.py
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/requirements.txt
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/netdash.json

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

# Create InfluxDB data source
curl -X POST -H "Content-Type: application/json" -d '{
    "name":"InfluxDB",
    "type":"influxdb",
    "url":"http://influxdb:8086",
    "access":"proxy",
    "database":"network_metrics"
}' ${GRAFANA_URL}/api/datasources -u ${GRAFANA_USER}:${GRAFANA_PASSWORD}

# Import Grafana dashboard
DASHBOARD_ID=$(curl -X POST -H "Content-Type: application/json" -d @netdash.json ${GRAFANA_URL}/api/dashboards/db -u ${GRAFANA_USER}:${GRAFANA_PASSWORD} | jq -r '.id')

print_success "Installation completed successfully!"
echo -e "${GREEN}You can access Grafana at http://localhost:9834 (default credentials: admin/admin)${NC}"
echo -e "${YELLOW}Please change the default password after your first login.${NC}"
echo -e "${YELLOW}Imported dashboard ID: ${DASHBOARD_ID}${NC}"

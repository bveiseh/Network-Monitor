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

print_status "Starting cleanup of Enhanced Network Monitor..."

# Check if we're in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found. Please run this script from the network-monitor directory."
fi

# Stop and remove containers
print_status "Stopping and removing Docker containers..."
docker-compose down -v

# Remove project files
print_status "Removing project files..."
cd ..
rm -rf network-monitor

print_success "Cleanup completed successfully!"
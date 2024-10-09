#!/bin/bash

set -e

echo "Starting installation of Enhanced Network Monitor..."

# Stop and remove existing services
sudo systemctl stop network-monitor.service || true
sudo systemctl disable network-monitor.service || true
sudo systemctl stop grafana-server || true

# Completely remove Grafana
sudo apt-get remove -y grafana
sudo apt-get autoremove -y
sudo rm -rf /var/lib/grafana /etc/grafana
sudo rm -f /etc/apt/sources.list.d/grafana.list

# Remove old installations
sudo rm -rf /home/pi/network_monitor
sudo rm -f /etc/systemd/system/network-monitor.service

# Add Grafana repository
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Remove old speedtest if present
sudo rm -f /etc/apt/sources.list.d/speedtest.list
sudo apt-get update
sudo apt-get remove -y speedtest speedtest-cli

# Install curl if not already installed
sudo apt-get install -y curl

# Add Ookla's official speedtest repository
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash

# Update and install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv grafana speedtest

# Ensure InfluxDB is running
if ! systemctl is-active --quiet influxdb; then
    echo "InfluxDB is not running. Attempting to start..."
    sudo systemctl start influxdb
    sudo systemctl enable influxdb
    
    # Wait for InfluxDB to start
    echo "Waiting for InfluxDB to start..."
    sleep 10
    
    if ! systemctl is-active --quiet influxdb; then
        echo "Failed to start InfluxDB. Please check the logs and ensure it's properly installed."
        exit 1
    fi
fi

echo "InfluxDB is running."

# Create InfluxDB database if it doesn't exist
if ! influx -execute "SHOW DATABASES" | grep -q "network_metrics"; then
    echo "Creating InfluxDB database 'network_metrics'..."
    influx -execute "CREATE DATABASE network_metrics" || {
        echo "Failed to create InfluxDB database. Please check if InfluxDB is configured correctly."
        exit 1
    }
else
    echo "InfluxDB database 'network_metrics' already exists."
fi

# Install required Python packages globally
sudo pip3 install --break-system-packages influxdb requests

# Use existing directory and Python script
cd /home/pi/peeng

# Create systemd service file
sudo tee /etc/systemd/system/network-monitor.service > /dev/null << EOL
[Unit]
Description=Enhanced Network Monitor
After=network.target influxdb.service grafana-server.service

[Service]
ExecStart=/usr/bin/python3 /home/pi/peeng/network_monitor.py
Restart=always
User=pi
WorkingDirectory=/home/pi/peeng

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd, enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable network-monitor.service
sudo systemctl start network-monitor.service

# Configure Grafana
# Wait for Grafana to be ready
echo "Waiting for Grafana to be ready..."
until $(curl --output /dev/null --silent --head --fail http://localhost:3000); do
    printf '.'
    sleep 5
done

# Set Grafana admin password
NEW_PASSWORD=$(openssl rand -base64 12)
curl -X PUT -H "Content-Type: application/json" -d "{
  \"oldPassword\": \"admin\",
  \"newPassword\": \"$NEW_PASSWORD\",
  \"confirmNew\": \"$NEW_PASSWORD\"
}" http://admin:admin@localhost:3000/api/user/password

echo "Grafana admin password has been set to: $NEW_PASSWORD"

# Add InfluxDB as a data source
curl -X POST -H "Content-Type: application/json" -d '{
    "name":"NetworkDB",
    "type":"influxdb",
    "url":"http://localhost:8086",
    "access":"proxy",
    "database":"network_metrics"
}' http://admin:$NEW_PASSWORD@localhost:3000/api/datasources

echo "Installation complete!"
echo "You can access Grafana at http://$(hostname -I | awk '{print $1}'):3000"
echo "Grafana login: admin / $NEW_PASSWORD"
echo "To change ping targets, edit the PING_TARGETS list in /home/pi/peeng/network_monitor.py"

# Check if the service is running
if systemctl is-active --quiet network-monitor.service; then
    echo "Network monitor service is running."
else
    echo "Network monitor service is not running. Please check the logs with: sudo journalctl -u network-monitor.service"
fi

# Display the last few lines of the log
echo "Last few lines of the network monitor log:"
sudo journalctl -u network-monitor.service -n 20 --no-pager
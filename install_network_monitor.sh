#!/bin/bash

set -e

echo "Starting installation of Enhanced Network Monitor..."

# Update and install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv curl wget gnupg2 apt-transport-https software-properties-common

# Install InfluxDB
echo "Installing InfluxDB..."
wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
echo "deb https://repos.influxdata.com/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
sudo apt-get update
sudo apt-get install -y influxdb

# Install Grafana
echo "Installing Grafana..."
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install -y grafana

# Install Ookla Speedtest CLI
echo "Installing Ookla Speedtest CLI..."
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
sudo apt-get install -y speedtest

# Install required Python packages
sudo pip3 install --break-system-packages influxdb requests

# Create InfluxDB database
echo "Creating InfluxDB database..."
sudo systemctl start influxdb
sudo systemctl enable influxdb
sleep 5  # Wait for InfluxDB to start
influx -execute "CREATE DATABASE network_metrics"

# Set up the network monitor service
echo "Setting up network monitor service..."
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

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable influxdb.service
sudo systemctl enable grafana-server.service
sudo systemctl enable network-monitor.service

# Start services
sudo systemctl start influxdb.service
sudo systemctl start grafana-server.service
sudo systemctl start network-monitor.service

# Configure Grafana
echo "Configuring Grafana..."
sleep 10  # Wait for Grafana to start

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

# Check if services are running
for service in influxdb grafana-server network-monitor; do
    if systemctl is-active --quiet $service; then
        echo "$service is running."
    else
        echo "$service is not running. Please check the logs with: sudo journalctl -u $service"
    fi
done

# Display the last few lines of the network monitor log
echo "Last few lines of the network monitor log:"
sudo journalctl -u network-monitor.service -n 20 --no-pager
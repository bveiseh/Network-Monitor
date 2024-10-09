#!/bin/bash

set -e

echo "Starting installation of Enhanced Network Monitor..."

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
sudo apt-get install -y python3-pip python3-venv influxdb grafana speedtest

# Create a virtual environment
python3 -m venv ~/network_monitor_env

# Activate the virtual environment and install Python dependencies
source ~/network_monitor_env/bin/activate
pip install influxdb

# Start and enable InfluxDB and Grafana services
sudo systemctl start influxdb
sudo systemctl start grafana-server
sudo systemctl enable influxdb
sudo systemctl enable grafana-server

# Create directory for the script
mkdir -p ~/network_monitor
cd ~/network_monitor

# Download the Python script
cat > network_monitor.py << EOL
import subprocess
import time
import speedtest
from influxdb import InfluxDBClient
from datetime import datetime
import logging
from collections import deque
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# InfluxDB configuration
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = 'network_metrics'

# Ping targets (configurable)
PING_TARGETS = ['8.8.8.8', '1.1.1.1']

# Connect to InfluxDB
client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT)
client.create_database(INFLUXDB_DATABASE)
client.switch_database(INFLUXDB_DATABASE)

MOVING_AVERAGE_WINDOW = 5

latency_deque = deque(maxlen=MOVING_AVERAGE_WINDOW)
speed_deque = deque(maxlen=MOVING_AVERAGE_WINDOW)

def calculate_moving_average(values):
    return sum(values) / len(values) if values else None

def measure_latency(target):
    try:
        logging.info(f"Measuring latency for {target}")
        output = subprocess.check_output(
            ['ping', '-c', '10', '-W', '2', target],
            universal_newlines=True,
            stderr=subprocess.STDOUT
        )
        lines = output.splitlines()
        latencies = []
        packets_transmitted = 0
        packets_received = 0
        
        for line in lines:
            if 'time=' in line:
                time_str = line.split('time=')[1].split()[0]
                latencies.append(float(time_str.rstrip('ms')))
            elif 'packets transmitted' in line:
                stats = line.split(', ')
                packets_transmitted = int(stats[0].split()[0])
                packets_received = int(stats[1].split()[0])
        
        if not latencies:
            logging.warning(f"No latency data found for {target}")
            return None
        
        packet_loss = 100.0 - (packets_received / packets_transmitted * 100)
        mdev = float(lines[-1].split('mdev = ')[1].split('/')[3].rstrip('ms'))
        
        result = {
            'min': min(latencies),
            'avg': sum(latencies) / len(latencies),
            'max': max(latencies),
            'mdev': mdev,
            'packet_loss': packet_loss
        }
        logging.info(f"Latency results for {target}: {result}")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Error measuring latency for {target}: {e.output}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error measuring latency for {target}: {str(e)}")
        return None

def average_latency_results(results):
    if not results:
        return None
    return {
        'min': sum(r['min'] for r in results) / len(results),
        'avg': sum(r['avg'] for r in results) / len(results),
        'max': sum(r['max'] for r in results) / len(results),
        'mdev': sum(r['mdev'] for r in results) / len(results),
        'packet_loss': sum(r['packet_loss'] for r in results) / len(results)
    }

def run_speed_test():
    try:
        output = subprocess.check_output(['speedtest', '--format=json'], universal_newlines=True)
        result = json.loads(output)
        return {
            'download': result['download']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'upload': result['upload']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'ping': result['ping']['latency']
        }
    except Exception as e:
        logging.error(f"Error running speed test: {e}")
        return None

def write_to_influxdb(measurement, fields):
    if measurement.startswith('latency'):
        latency_deque.append(fields)
        avg_fields = {
            'min': calculate_moving_average([d['min'] for d in latency_deque]),
            'avg': calculate_moving_average([d['avg'] for d in latency_deque]),
            'max': calculate_moving_average([d['max'] for d in latency_deque]),
            'mdev': calculate_moving_average([d['mdev'] for d in latency_deque]),
            'packet_loss': calculate_moving_average([d['packet_loss'] for d in latency_deque])
        }
        fields = avg_fields
    elif measurement == 'speed_test':
        speed_deque.append(fields)
        avg_fields = {
            'download': calculate_moving_average([d['download'] for d in speed_deque]),
            'upload': calculate_moving_average([d['upload'] for d in speed_deque]),
            'ping': calculate_moving_average([d['ping'] for d in speed_deque])
        }
        fields = avg_fields

    json_body = [
        {
            "measurement": measurement,
            "tags": {
                "host": "raspberry_pi"
            },
            "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "fields": fields
        }
    ]
    client.write_points(json_body)

def main():
    last_speed_test_time = 0
    while True:
        try:
            current_time = int(time.time())
            
            # Measure and write latency for both targets
            latency_results = [measure_latency(target) for target in PING_TARGETS]
            latency_results = [r for r in latency_results if r is not None]
            
            if latency_results:
                avg_latency = average_latency_results(latency_results)
                write_to_influxdb("latency", avg_latency)
                logging.info(f"Wrote average latency to InfluxDB: {avg_latency}")
                
                # Write individual target results
                for target, result in zip(PING_TARGETS, latency_results):
                    write_to_influxdb(f"latency_{target}", result)
                    logging.info(f"Wrote latency for {target} to InfluxDB: {result}")
            else:
                logging.warning("No valid latency results to write to InfluxDB")

            # Run speed test every 5 seconds
            if current_time - last_speed_test_time >= 5:
                speed = run_speed_test()
                if speed:
                    write_to_influxdb("speed_test", speed)
                    logging.info(f"Wrote speed test results to InfluxDB: {speed}")
                last_speed_test_time = current_time

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")

        time.sleep(1)  # Wait for 1 second before the next measurement

if __name__ == "__main__":
    logging.info("Starting Enhanced Network Monitor")
    main()
EOL

# Create systemd service file
sudo tee /etc/systemd/system/network-monitor.service > /dev/null << EOL
[Unit]
Description=Enhanced Network Monitor
After=network.target

[Service]
ExecStart=/home/pi/network_monitor_env/bin/python3 /home/pi/network_monitor/network_monitor.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the service
sudo systemctl enable network-monitor.service
sudo systemctl start network-monitor.service

# Configure Grafana
# Wait for Grafana to be ready
echo "Waiting for Grafana to be ready..."
until $(curl --output /dev/null --silent --head --fail http://localhost:3000); do
    printf '.'
    sleep 5
done

# Add InfluxDB as a data source
curl -X POST -H "Content-Type: application/json" -d '{
    "name":"NetworkDB",
    "type":"influxdb",
    "url":"http://localhost:8086",
    "access":"proxy",
    "database":"network_metrics"
}' http://admin:admin@localhost:3000/api/datasources

# Create dashboard
DASHBOARD_JSON=$(cat << 'EOL'
{
  "dashboard": {
    "id": null,
    "title": "Enhanced Network Monitor Dashboard",
    "tags": [ "network" ],
    "timezone": "browser",
    "panels": [
      {
        "title": "Current Average Latency",
        "type": "gauge",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT last(\"avg\") FROM \"latency\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0}
      },
      {
        "title": "Latency Over Time (Combined)",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"min\") AS \"Min\", mean(\"avg\") AS \"Avg\", mean(\"max\") AS \"Max\" FROM \"latency\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "tooltip": {
          "shared": true,
          "sort": 0,
          "value_type": "individual"
        },
        "gridPos": {"h": 8, "w": 16, "x": 8, "y": 0}
      },
      {
        "title": "Latency Comparison (Line Chart)",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"avg\") FROM \"latency_8.8.8.8\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true,
            "alias": "8.8.8.8"
          },
          {
            "query": "SELECT mean(\"avg\") FROM \"latency_1.1.1.1\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true,
            "alias": "1.1.1.1"
          }
        ],
        "tooltip": {
          "shared": true,
          "sort": 0,
          "value_type": "individual"
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "title": "Latency Jitter",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"mdev\") FROM \"latency\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      },
      {
        "title": "Download Speed",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"download\") FROM \"speed_test\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 16}
      },
      {
        "title": "Upload Speed",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"upload\") FROM \"speed_test\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 8, "x": 8, "y": 16}
      },
      {
        "title": "Speedtest Ping",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"ping\") FROM \"speed_test\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 8, "x": 16, "y": 16}
      },
      {
        "title": "Packet Loss",
        "type": "graph",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT mean(\"packet_loss\") FROM \"latency\" WHERE $timeFilter GROUP BY time($__interval) fill(null)",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24}
      },
      {
        "title": "Network Stats",
        "type": "table",
        "datasource": "NetworkDB",
        "targets": [
          {
            "query": "SELECT last(\"avg\") as \"Avg Latency (ms)\", last(\"download\") as \"Download (Mbps)\", last(\"upload\") as \"Upload (Mbps)\" FROM (SELECT * FROM latency), (SELECT * FROM speed_test) WHERE $timeFilter",
            "rawQuery": true
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24}
      }
    ],
    "schemaVersion": 16,
    "version": 0,
    "time": {
      "from": "now-6h",
      "to": "now"
    },
    "timepicker": {
      "refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "1d"],
      "time_options": ["5m", "15m", "1h", "6h", "12h", "24h", "2d", "7d", "30d"]
    }
  },
  "folderId": 0,
  "overwrite": false
}
EOL
)

curl -X POST -H "Content-Type: application/json" -d "${DASHBOARD_JSON}" http://admin:admin@localhost:3000/api/dashboards/db

echo "Installation complete!"
echo "You can access Grafana at http://$(hostname -I | awk '{print $1}'):3000"
echo "Default login: admin/admin"
echo "Please change the default password after your first login."
echo "To change ping targets, edit the PING_TARGETS list in /home/pi/network_monitor/network_monitor.py"
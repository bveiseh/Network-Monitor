
# Enhanced Network Monitor

## Overview

The Enhanced Network Monitor is a Python-based tool designed to continuously monitor network performance metrics, including latency, packet loss, and internet speed. It stores the collected data in InfluxDB and provides visualization through Grafana dashboards.

## Features

- Measures latency to multiple configurable targets
- Conducts regular speed tests
- Calculates moving averages for smoother data representation
- Stores data in InfluxDB for efficient time-series storage
- Provides a pre-configured Grafana dashboard for data visualization

## Prerequisites

- Raspberry Pi (or similar Linux-based system)
- Python 3.6+
- InfluxDB
- Grafana
- Speedtest CLI

## Installation

1. Clone this repository or download the installation script.

2. Make the installation script executable:
   ```
   chmod +x install_network_monitor.sh
   ```

3. Run the installation script:
   ```
   ./install_network_monitor.sh
   ```

The script will:
- Install necessary packages (Python3, pip, InfluxDB, Grafana, Speedtest CLI)
- Set up a Python virtual environment
- Install required Python packages
- Configure InfluxDB and Grafana
- Create and start a systemd service for the network monitor

## Configuration

The main configuration options are in the `network_monitor.py` file:


```12:18:network_monitor.py
# InfluxDB configuration
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = 'network_metrics'

# Ping targets (configurable)
PING_TARGETS = ['8.8.8.8', '1.1.1.1']
```


- `INFLUXDB_HOST`: InfluxDB server address (default: 'localhost')
- `INFLUXDB_PORT`: InfluxDB port (default: 8086)
- `INFLUXDB_DATABASE`: InfluxDB database name (default: 'network_metrics')
- `PING_TARGETS`: List of IP addresses or hostnames to ping for latency measurements

## Usage

The network monitor service should start automatically after installation. You can manage it using systemd commands:

```
sudo systemctl start network-monitor.service
sudo systemctl stop network-monitor.service
sudo systemctl restart network-monitor.service
sudo systemctl status network-monitor.service
```

## Accessing the Dashboard

1. Open a web browser and go to `http://<your-raspberry-pi-ip>:3000`
2. Log in with the default credentials (username: admin, password: admin)
3. You will be prompted to change the password on first login
4. Navigate to the "Enhanced Network Monitor Dashboard"

## What to Expect

- The dashboard provides real-time and historical data on network performance
- Latency measurements are taken continuously
- Speed tests are conducted every 5 minutes
- Moving averages are calculated to smooth out data fluctuations

## Troubleshooting

- Check the system logs for any errors:
  ```
  sudo journalctl -u network-monitor.service
  ```
- Ensure InfluxDB and Grafana services are running:
  ```
  sudo systemctl status influxdb
  sudo systemctl status grafana-server
  ```

## Customization

- To change ping targets, edit the `PING_TARGETS` list in `/home/pi/network_monitor/network_monitor.py`
- To modify the dashboard, use the Grafana web interface

## Notes

- The tool uses significant bandwidth due to regular speed tests. Consider this if you have limited data plans.
- Continuous monitoring may impact the performance of the Raspberry Pi. Monitor system resources if you experience issues.
- Ensure your Raspberry Pi has a stable power supply to prevent data corruption during writes to InfluxDB.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

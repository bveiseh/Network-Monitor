# Network Monitor

## Overview

Network Monitor is a Python-based tool designed to continuously monitor network performance metrics, including latency, packet loss, and internet speed. It stores the collected data in InfluxDB and provides visualization through Grafana dashboards. A unique feature of this tool is its ability to generate AI-powered network reports using various Language Model (LLM) providers.

## Features

- Measures latency to multiple configurable targets
- Conducts regular speed tests
- Stores data in InfluxDB for efficient time-series storage
- Provides a pre-configured Grafana dashboard for data visualization
- Generates AI-powered network reports using configurable LLM providers

## Installation

1. Ensure you have sudo privileges on your system.

2. Clone the repository:
   ```
   git clone https://github.com/bveiseh/Network-Monitor.git
   cd Network-Monitor
   ```

3. Make the installation script executable:
   ```
   chmod +x install.sh
   ```

4. Run the installation script:
   ```
   sudo ./install.sh
   ```

5. Follow the prompts to configure your network monitor:
   - Choose your preferred LLM provider (Ollama, OpenAI, Anthropic, or Custom)
   - Enter the required details for your chosen LLM provider
   - Specify your ping targets (defaults are provided)
   - Enter your Grafana API key

## Usage

To start monitoring, run:

```
sudo network-monitor --start
```

## Accessing the Dashboard

1. Determine your device's IP address:
   ```
   hostname -I | awk '{print $1}'
   ```

2. Open a web browser and go to `http://<device_ip>:3000` (replace `<device_ip>` with your device's IP address).

3. Log in with the default credentials (username: admin, password: admin).

4. You will be prompted to change the password on first login.

5. Navigate to the "Network Monitor Dashboard".

## Troubleshooting

If you encounter issues during installation or operation, try the following steps:

1. Check system logs:
   ```
   sudo journalctl -u network-monitor
   ```

2. Verify service status:
   ```
   sudo systemctl status influxdb grafana-server
   ```

3. Check InfluxDB and Grafana logs:
   ```
   sudo journalctl -u influxdb
   sudo journalctl -u grafana-server
   ```

If you're still experiencing issues, please open an issue on the [GitHub repository](https://github.com/bveiseh/Network-Monitor) with detailed information about your setup and the problem you're encountering.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

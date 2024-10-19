# AI Network Monitor

## Overview

The Enhanced Network Monitor is a Python-based tool designed to continuously monitor network performance metrics, including latency, packet loss, and internet speed. It stores the collected data in InfluxDB and provides visualization through Grafana dashboards. A unique feature of this tool is its ability to generate AI-powered network reports using various Language Model (LLM) providers.

## Features

- Measures latency to multiple configurable targets
- Conducts regular speed tests
- Calculates moving averages for smoother data representation
- Stores data in InfluxDB for efficient time-series storage
- Provides a pre-configured Grafana dashboard for data visualization
- Generates AI-powered network reports using configurable LLM providers

## Installation

Choose one of the following installation methods based on your preference and system setup:

### Option 1: Using Docker (Recommended)

1. Ensure you have Docker and Docker Compose installed on your system.

2. Clone the repository:
   ```
   git clone https://github.com/bveiseh/Network-Monitor.git
   cd Network-Monitor
   ```

3. Run the Docker installation script:
   ```
   ./install_network_monitor.sh
   ```

4. Follow the prompts to configure your network monitor:
   - Choose your preferred LLM provider (Ollama, OpenAI, Anthropic, or Custom)
   - Enter the required details for your chosen LLM provider
   - Specify your ping targets (defaults are provided)

5. The installation script will:
   - Start the necessary Docker containers (InfluxDB, Grafana, and the network monitor)
   - Configure Grafana with an automatically generated API key
   - Import the pre-configured dashboard

6. Access Grafana at `http://localhost:9834` (default credentials: admin/admin)

### Option 2: Using Bash (Direct Installation)

1. Ensure you have sudo privileges on your system.

2. Clone the repository:
   ```
   git clone https://github.com/yourusername/enhanced-network-monitor.git
   cd enhanced-network-monitor
   ```

3. Run the Bash installation script:
   ```
   sudo ./install_network_monitor_bash.sh
   ```

4. Follow the prompts to configure your network monitor (same as in the Docker installation)

5. The script will:
   - Install necessary packages
   - Set up a Python virtual environment
   - Install required Python packages
   - Configure InfluxDB and Grafana
   - Create and start a systemd service for the network monitor

6. Access Grafana at `http://localhost:3000` (default credentials: admin/admin)

## Configuration

The Enhanced Network Monitor features an interactive configuration process that allows you to easily set up all aspects of the system. During the installation, you'll be prompted to configure:

### LLM Provider

Choose from one of the following options:

1. **Ollama (Recommended)**: A local LLM option. You'll need to provide the Ollama URL and model name.
   - Recommended setup: Run Ollama on the same server as this network monitor, or use a remote/local network Ollama server.
   - Suggested model: `llama3.1:8b-instruct`
   - This option is the most cost-effective, private, and secure.

2. **OpenAI**: Uses OpenAI's API. You'll need to provide your API key and the model name.
   - Suggested model: `gpt-4o-mini`

3. **Anthropic**: Uses Anthropic's API. You'll need to provide your API key and the model name.
   - Suggested model: `claude-3-sonnet`

4. **Custom**: Allows you to use any LLM provider that supports the OpenAI API format. You'll need to provide the API URL, key, and model name.

### Ping Targets

You'll be prompted to enter up to three ping targets:
1. First target (default: 1.1.1.1)
2. Second target (default: 8.8.8.8)
3. Your gateway IP address (default: 10.1.1.1)

It's recommended to include your gateway IP address to monitor your local network performance.

All of these configuration options are saved to a `network_monitor_config.json` file, which is used to persist your settings between runs.

## Usage

Once configured and running, the network monitor will continuously collect data and store it in InfluxDB. You can view the data and AI-generated reports through the Grafana dashboard.

### For Docker installations:

```bash
docker-compose start   # Start all services
docker-compose stop    # Stop all running services
docker-compose restart # Restart all services
docker-compose logs    # View logs from all services
```

### For Bash installations:

```bash
sudo systemctl start network-monitor   # Start the network monitor service
sudo systemctl stop network-monitor    # Stop the network monitor service
sudo systemctl restart network-monitor # Restart the network monitor service
sudo systemctl status network-monitor  # Check the current status of the service
```

## Accessing the Dashboard

1. Open a web browser and go to:
   - Docker installation: `http://localhost:9834`
   - Bash installation: `http://localhost:3000`
2. Log in with the default credentials (username: admin, password: admin)
3. You will be prompted to change the password on first login
4. Navigate to the "Enhanced Network Monitor Dashboard"

## Troubleshooting

If you encounter issues during installation or operation, try the following steps:

1. Check system logs:
   - For Docker installations: `docker-compose logs`
   - For Bash installations: `sudo journalctl -u network-monitor`

2. Verify service status:
   - For Docker: `docker ps` to check if all containers are running
   - For Bash: `sudo systemctl status network-monitor influxdb grafana-server`

3. Port conflicts:
   - If you see errors about ports being in use, you may need to modify the port mappings in `docker-compose.yml` (for Docker installations) or the service configurations (for Bash installations).

4. Permission issues:
   - Ensure you're running the installation scripts with appropriate permissions (sudo for Bash installation).

5. Network issues:
   - If the network monitor can't reach the internet, check your firewall settings and ensure the necessary ports are open.

6. LLM provider issues:
   - Verify that your API keys and URLs for the chosen LLM provider are correct.
   - Check the provider's status page for any ongoing issues.

7. InfluxDB or Grafana issues:
   - Check their respective logs:
     - Docker: `docker logs influxdb` or `docker logs grafana`
     - Bash: `sudo journalctl -u influxdb` or `sudo journalctl -u grafana-server`

If you're still experiencing issues, please open an issue on the GitHub repository with detailed information about your setup and the problem you're encountering.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

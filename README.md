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

### Option 1: Using Docker (Recommended)

1. Ensure you have Docker and Docker Compose installed on your system.

2. Clone the repository:
   ```
   git clone https://github.com/yourusername/enhanced-network-monitor.git
   cd enhanced-network-monitor
   ```

3. Start the services:
   ```
   docker-compose up -d
   ```

4. Access Grafana at `http://localhost:9834` (default credentials: admin/admin)

### Option 2: Using Bash (Manual Installation)

1. Ensure you have Python 3.6+ installed on your system.

2. Clone the repository:
   ```
   git clone https://github.com/yourusername/enhanced-network-monitor.git
   cd enhanced-network-monitor
   ```

3. Make the installation script executable:
   ```
   chmod +x install_network_monitor.sh
   ```

4. Run the installation script:
   ```
   ./install_network_monitor.sh
   ```

5. The script will install necessary packages, set up a Python virtual environment, install required Python packages, configure InfluxDB and Grafana, and create a systemd service for the network monitor.

6. Access Grafana at `http://localhost:3000` (default credentials: admin/admin)

## Configuration

### Basic Configuration

The main configuration options are in the `network_monitor.py` file:

```python
# InfluxDB configuration
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 9834
INFLUXDB_DATABASE = 'network_metrics'

# Ping targets (configurable)
PING_TARGETS = ['8.8.8.8', '1.1.1.1', '10.1.1.1']
```

### LLM Configuration

One of the unique features of this network monitor is its ability to generate AI-powered network reports using various Language Model (LLM) providers. When you start the application, you'll be prompted to configure your preferred LLM provider.

To configure the LLM:

1. Start the network monitor application.
2. You'll see the following prompt:
   ```
   LLM Configuration
   1. Ollama (Recommended)
   2. OpenAI
   3. Anthropic
   4. Custom (OpenAI API format)
   Select LLM provider (1-4):
   ```
3. Enter the number corresponding to your preferred LLM provider.
4. Follow the subsequent prompts to enter the necessary details (API key, model name, etc.) for your chosen provider.

#### LLM Provider Options:

1. **Ollama (Recommended)**: A local LLM option. You'll need to provide the Ollama URL and model name.
   - Recommended setup: Run Ollama on the same server as this network monitor, or use a remote/local network Ollama server.
   - Suggested model: `llama3.1:8b-instruct`
   - This option is the most cost-effective, private, and secure.

2. **OpenAI**: Uses OpenAI's API. You'll need to provide your API key and the model name.
   - Suggested model: `gpt-4o-mini`

3. **Anthropic**: Uses Anthropic's API. You'll need to provide your API key and the model name.
   - Suggested model: `claude-3-sonnet`

4. **Custom**: Allows you to use any LLM provider that supports the OpenAI API format. You'll need to provide the API URL, key, and model name.

#### Model Recommendations:

For this network monitoring application, smaller models are generally sufficient as the tasks are not highly sophisticated. However, using more advanced models can improve the quality and insights of the generated reports.

We recommend starting with smaller models (like the suggested ones above) and scaling up if you need more detailed or nuanced reports. The Ollama option with `llama3.1:8b-instruct` provides a good balance of performance, privacy, and resource usage for most use cases.

## AI-Powered Network Reports

The AI-powered network reports are a key feature of this monitor. Every 15 minutes, the system generates a concise, professional summary of the network's performance using the configured LLM. These reports:

- Analyze the last 24 hours of latency and speed test data
- Focus on significant issues, trends, or anomalies
- Highlight any sustained issues or frequent disconnects
- Provide a quick, high-level overview of network health

These AI-generated reports offer a unique, intelligent insight into your network's performance, complementing the raw data and visualizations provided by the monitoring system.

## Usage

Once configured and running, the network monitor will continuously collect data and store it in InfluxDB. You can view the data and AI-generated reports through the Grafana dashboard. Here are the commands to manage the network monitor service:

### For Docker installations:

```bash
docker-compose start   # Start all services defined in docker-compose.yml
docker-compose stop    # Stop all running services
docker-compose restart # Restart all services
docker-compose logs    # View logs from all services
```

These commands allow you to:
- Start the network monitor and associated services (InfluxDB, Grafana) if they're not running.
- Stop all services gracefully when you need to pause monitoring.
- Restart all services, which can be useful after configuration changes.
- View the logs of all services, which is crucial for troubleshooting and monitoring the application's behavior.

### For Bash installations:

```bash
sudo systemctl start network-monitor.service   # Start the network monitor service
sudo systemctl stop network-monitor.service    # Stop the network monitor service
sudo systemctl restart network-monitor.service # Restart the network monitor service
sudo systemctl status network-monitor.service  # Check the current status of the service
```

These commands allow you to:
- Start the network monitor service if it's not already running.
- Stop the service when you need to pause monitoring or make configuration changes.
- Restart the service, which is useful after making changes or if you suspect any issues.
- Check the current status of the service, including whether it's running, stopped, or encountering any errors.

Using these commands, you can easily manage the network monitor, ensuring it's running when you need it and allowing you to troubleshoot any issues that may arise.

## Accessing the Dashboard

1. Open a web browser and go to:
   - Docker installation: `http://localhost:9834`
   - Bash installation: `http://localhost:3000`
2. Log in with the default credentials (username: admin, password: admin)
3. You will be prompted to change the password on first login
4. Navigate to the "Enhanced Network Monitor Dashboard"

## Troubleshooting

- For Docker installations, check the logs:
  ```
  docker-compose logs network-monitor
  ```
- For Bash installations, check the system logs:
  ```
  sudo journalctl -u network-monitor.service
  ```
- Ensure InfluxDB and Grafana services are running

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

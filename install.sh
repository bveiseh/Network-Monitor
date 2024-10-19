#!/bin/bash

set -e

echo "Installing Network Monitor..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Install required system packages
sudo apt-get update
sudo apt-get install -y python3-pip influxdb grafana speedtest-cli

# Install Python dependencies
pip3 install influxdb requests

# Download the network_monitor.py script
curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/network_monitor.py

# Make the script executable
chmod +x network_monitor.py

# Move the script to a suitable location
sudo mv network_monitor.py /usr/local/bin/network-monitor

# Start and enable InfluxDB and Grafana services
sudo systemctl start influxdb
sudo systemctl enable influxdb
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Configuration
echo "Configuring Network Monitor..."

# LLM Configuration
echo "LLM Configuration"
echo "1. Ollama"
echo "2. OpenAI"
echo "3. Anthropic"
echo "4. Custom (OpenAI API format)"

read -p "Select LLM provider (1-4): " llm_choice

case $llm_choice in
    1)
        read -p "Enter Ollama URL (default: http://localhost:11434): " ollama_url
        ollama_url=${ollama_url:-http://localhost:11434}
        read -p "Enter Ollama model name: " ollama_model
        llm_config="{\"provider\": \"ollama\", \"url\": \"$ollama_url\", \"model\": \"$ollama_model\"}"
        ;;
    2)
        read -p "Enter OpenAI API key: " openai_key
        read -p "Enter OpenAI model name (e.g., gpt-4o-mini): " openai_model
        llm_config="{\"provider\": \"openai\", \"api_key\": \"$openai_key\", \"model\": \"$openai_model\"}"
        ;;
    3)
        read -p "Enter Anthropic API key: " anthropic_key
        read -p "Enter Anthropic model name (e.g., claude-3-sonnet): " anthropic_model
        llm_config="{\"provider\": \"anthropic\", \"api_key\": \"$anthropic_key\", \"model\": \"$anthropic_model\"}"
        ;;
    4)
        read -p "Enter custom LLM API URL: " custom_url
        read -p "Enter API key (if required): " custom_key
        read -p "Enter model name: " custom_model
        llm_config="{\"provider\": \"custom\", \"url\": \"$custom_url\", \"api_key\": \"$custom_key\", \"model\": \"$custom_model\"}"
        ;;
    *)
        echo "Invalid choice. Using default Ollama configuration."
        llm_config="{\"provider\": \"ollama\", \"url\": \"http://localhost:11434\", \"model\": \"llama2\"}"
        ;;
esac

# Ping Target Configuration
echo "Ping Target Configuration"
read -p "Enter first ping target (default: 1.1.1.1): " target1
target1=${target1:-1.1.1.1}
read -p "Enter second ping target (default: 8.8.8.8): " target2
target2=${target2:-8.8.8.8}
read -p "Enter your gateway IP address (default: 10.1.1.1): " gateway
gateway=${gateway:-10.1.1.1}

# Grafana API Key Configuration
echo "Grafana API Key Configuration"
read -p "Enter your Grafana API key: " grafana_api_key

# Create configuration file
config_path="/etc/network_monitor_config.json"
sudo tee $config_path > /dev/null << EOF
{
  "llm": $llm_config,
  "ping_targets": ["$target1", "$target2", "$gateway"],
  "grafana_api_key": "$grafana_api_key"
}
EOF

echo "Configuration saved to $config_path"

echo "Installation complete!"
echo "To start monitoring, run: sudo network-monitor --start"

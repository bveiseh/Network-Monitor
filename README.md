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

2. Download the installation script:
   ```
   curl -O https://raw.githubusercontent.com/yourusername/network-monitor/main/install.sh
   ```

3. Make the script executable:
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

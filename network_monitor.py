import subprocess
import time
from influxdb import InfluxDBClient
from datetime import datetime, timedelta
import logging
import json
import requests
import argparse
import os
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# InfluxDB configuration
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = 'network_metrics'

# Grafana configuration
GRAFANA_HOST = 'http://localhost:3000'
DASHBOARD_UID = 'fe0atovlm7o5cd'

# Global variables to be set by configuration
PING_TARGETS = []
GRAFANA_API_KEY = ''
LLM_CONFIG = {}

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
        
        packet_loss = 100.0 - (packets_received / packets_transmitted * 100)
        
        if not latencies:
            logging.warning(f"No latency data found for {target}")
            return {
                'target': target,
                'min': float('inf'),
                'avg': float('inf'),
                'max': float('inf'),
                'mdev': float('inf'),
                'packet_loss': 100.0,
                'status': 'disconnected'
            }
        
        # Extract mdev (standard deviation) from the last line
        mdev = 0.0
        try:
            mdev = float(lines[-1].split('mdev = ')[1].split('/')[3].rstrip(' ms'))
        except IndexError:
            logging.warning(f"Could not extract mdev for {target}")
        
        result = {
            'target': target,
            'min': min(latencies),
            'avg': sum(latencies) / len(latencies),
            'max': max(latencies),
            'mdev': mdev,
            'packet_loss': packet_loss,
            'status': 'connected' if packet_loss < 100 else 'disconnected'
        }
        logging.info(f"Latency results for {target}: {result}")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Error measuring latency for {target}: {e.output}")
        return {
            'target': target,
            'min': float('inf'),
            'avg': float('inf'),
            'max': float('inf'),
            'mdev': float('inf'),
            'packet_loss': 100.0,
            'status': 'disconnected'
        }
    except Exception as e:
        logging.error(f"Unexpected error measuring latency for {target}: {str(e)}")
        return {
            'target': target,
            'min': float('inf'),
            'avg': float('inf'),
            'max': float('inf'),
            'mdev': float('inf'),
            'packet_loss': 100.0,
            'status': 'disconnected'
        }

def run_speed_test():
    try:
        output = subprocess.check_output(['speedtest', '-f', 'json'], universal_newlines=True)
        result = json.loads(output)
        return {
            'download': result['download']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'upload': result['upload']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'ping': result['ping']['latency'],
            'jitter': result['ping']['jitter'],
            'latency_idle': result['ping']['low'],
            'latency_download': result['download']['latency']['low'],
            'latency_upload': result['upload']['latency']['low'],
            'latency_idle_high': result['ping']['high'],
            'latency_download_high': result['download']['latency']['high'],
            'latency_upload_high': result['upload']['latency']['high'],
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running speed test: {e.output}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing speed test JSON output: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error running speed test: {str(e)}")
        return None

def write_to_influxdb(measurement, fields):
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
    response = client.write_points(json_body)
    logging.info(f"InfluxDB write response: {response}")

def generate_network_report(extended_data, llm_config):
    prompt = f"""
    You are a highly advanced, professional AI network monitoring system. Your task is to analyze network performance data and provide a concise, factual summary focusing only on significant issues or trends. Use the following data for your analysis:

    Latency Data (last 24 hours):
    {json.dumps(extended_data['latency_24h'], indent=2)}

    Speed Test Data (last 24 hours):
    {json.dumps(extended_data['speed_24h'], indent=2)}

    Network Status:
    Disconnects (24h): {extended_data['disconnects_24h']}

    Sustained Issues (latency > 100ms for > 5 minutes):
    {json.dumps(extended_data['sustained_issues'], indent=2)}

    Guidelines:
    1. Provide a brief, professional summary in 2-3 sentences.
    2. Focus only on significant deviations, issues, or trends, particularly in the last hour.
    3. Do not mention specific numbers unless there's a notable issue or extreme spike.
    4. Maintain a serious, formal tone throughout the report.
    5. If there are no significant issues, provide a brief "normal operations" message.
    6. Highlight any sustained issues or frequent disconnects if present.
    7. Pay special attention to sudden spikes or drops in latency or speed.
    8. Remember that gradual increases in latency are not typical; focus on significant fluctuations.
    9. Do not provide any advice or suggestions for fixes.

    Your response should be brief and informative, suitable for a quick network health assessment by a technical professional. Only mention specific data points if they represent a significant issue or anomaly.
    """

    try:
        if llm_config['provider'] == 'ollama':
            response = requests.post(f"{llm_config['url']}/api/generate", json={
                "model": llm_config['model'],
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "max_tokens": 150
                }
            }, timeout=200)
            response.raise_for_status()
            report = response.json().get('response', '').strip()
        elif llm_config['provider'] == 'openai':
            openai.api_key = llm_config['api_key']
            response = openai.Completion.create(
                engine=llm_config['model'],
                prompt=prompt,
                max_tokens=150,
                temperature=0.3
            )
            report = response.choices[0].text.strip()
        elif llm_config['provider'] == 'anthropic':
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": llm_config['api_key']
            }
            data = {
                "prompt": prompt,
                "model": llm_config['model'],
                "max_tokens_to_sample": 150,
                "temperature": 0.3
            }
            response = requests.post("https://api.anthropic.com/v1/complete", headers=headers, json=data, timeout=200)
            response.raise_for_status()
            report = response.json().get('completion', '').strip()
        elif llm_config['provider'] == 'custom':
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_config['api_key']}"
            }
            data = {
                "model": llm_config['model'],
                "prompt": prompt,
                "max_tokens": 150,
                "temperature": 0.3
            }
            response = requests.post(llm_config['url'], headers=headers, json=data, timeout=200)
            response.raise_for_status()
            report = response.json().get('choices', [{}])[0].get('text', '').strip()
        
        # Post-process the report
        sentences = report.split('.')
        if len(sentences) > 3:
            report = '. '.join(sentences[:3]) + '.'
        
        return report.strip()
    except Exception as e:
        logging.error(f"Error generating network report: {str(e)}")
        return "Network report unavailable due to a temporary issue."

def configure():
    config = {}
    print("Network Monitor Configuration")
    
    # LLM Configuration
    print("\nLLM Configuration")
    print("1. Ollama")
    print("2. OpenAI")
    print("3. Anthropic")
    print("4. Custom (OpenAI API format)")
    
    choice = input("Select LLM provider (1-4): ")
    
    if choice == '1':
        url = input("Enter Ollama URL (default: http://localhost:11434): ") or "http://localhost:11434"
        model = input("Enter Ollama model name: ")
        config['llm'] = {'provider': 'ollama', 'url': url, 'model': model}
    elif choice == '2':
        api_key = input("Enter OpenAI API key: ")
        model = input("Enter OpenAI model name (e.g., gpt-4o-mini): ")
        config['llm'] = {'provider': 'openai', 'api_key': api_key, 'model': model}
    elif choice == '3':
        api_key = input("Enter Anthropic API key: ")
        model = input("Enter Anthropic model name (e.g., claude-3-sonnet): ")
        config['llm'] = {'provider': 'anthropic', 'api_key': api_key, 'model': model}
    elif choice == '4':
        url = input("Enter custom LLM API URL: ")
        api_key = input("Enter API key (if required): ")
        model = input("Enter model name: ")
        config['llm'] = {'provider': 'custom', 'url': url, 'api_key': api_key, 'model': model}
    else:
        print("Invalid choice. Using default Ollama configuration.")
        config['llm'] = {'provider': 'ollama', 'url': "http://localhost:11434", 'model': "llama2"}

    # Configure ping targets
    print("\nPing Target Configuration")
    targets = []
    targets.append(input("Enter first ping target (default: 1.1.1.1): ") or "1.1.1.1")
    targets.append(input("Enter second ping target (default: 8.8.8.8): ") or "8.8.8.8")
    gateway = input("Enter your gateway IP address (default: 10.1.1.1): ") or "10.1.1.1"
    targets.append(gateway)
    config['ping_targets'] = targets

    # Grafana API Key Configuration
    print("\nGrafana API Key Configuration")
    grafana_api_key = input("Enter your Grafana API key: ")
    config['grafana_api_key'] = grafana_api_key

    # Save configuration to file
    config_path = os.path.expanduser('~/.network_monitor_config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Configuration saved to {config_path}")
    return config

def load_configuration():
    config_path = os.path.expanduser('~/.network_monitor_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return None

def main():
    global PING_TARGETS, GRAFANA_API_KEY, LLM_CONFIG

    parser = argparse.ArgumentParser(description="Network Monitor")
    parser.add_argument("--configure", action="store_true", help="Run configuration wizard")
    parser.add_argument("--start", action="store_true", help="Start monitoring")
    args = parser.parse_args()

    if args.configure:
        configure()
        sys.exit(0)

    if args.start:
        config = load_configuration()
        if not config:
            print("No configuration found. Please run with --configure first.")
            sys.exit(1)

        PING_TARGETS = config['ping_targets']
        GRAFANA_API_KEY = config['grafana_api_key']
        LLM_CONFIG = config['llm']

        # Initialize InfluxDB client
        client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT)
        client.create_database(INFLUXDB_DATABASE)
        client.switch_database(INFLUXDB_DATABASE)

        print("Starting network monitoring...")
        while True:
            for target in PING_TARGETS:
                latency = measure_latency(target)
                write_to_influxdb(f"latency_{target}", latency)

            time.sleep(60)  # Wait for 1 minute before next measurement

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
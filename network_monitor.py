import subprocess
import time
from influxdb import InfluxDBClient
from datetime import datetime
import logging
from collections import deque
import json
import requests

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

# Grafana configuration
GRAFANA_HOST = 'http://localhost:3000'
DASHBOARD_UID = 'fe0atovlm7o5cd'
GRAFANA_API_KEY = 'glsa_VMUyp1G9lnCSe3gy42Nk0tT0qbUd8N2T_980a759f'

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
        
        # Extract mdev (standard deviation) from the last line
        mdev = 0.0
        try:
            mdev = float(lines[-1].split('mdev = ')[1].split('/')[3].rstrip(' ms'))
        except IndexError:
            logging.warning(f"Could not extract mdev for {target}")
        
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

def measure_buffer_bloat():
    try:
        # Run iperf3 test to simulate network load
        subprocess.Popen(['iperf3', '-c', 'iperf.he.net', '-t', '30', '-P', '3'], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Measure latency during the iperf3 test
        output = subprocess.check_output(['ping', '-c', '30', '-i', '1', '8.8.8.8'], universal_newlines=True)
        
        latencies = [float(line.split('time=')[1].split()[0]) for line in output.splitlines() if 'time=' in line]
        
        if not latencies:
            return None
        
        return {
            'min': min(latencies),
            'avg': sum(latencies) / len(latencies),
            'max': max(latencies),
            'mdev': float(output.splitlines()[-1].split('mdev = ')[1].split('/')[3].rstrip(' ms'))
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error measuring buffer bloat: {e.output}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error measuring buffer bloat: {str(e)}")
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
    client.write_points(json_body)

def setup_grafana_dashboard():
    logging.info("Setting up Grafana dashboard")
    
    # Create a new dashboard
    dashboard = {
        "dashboard": {
            "id": None,
            "uid": None,
            "title": "Network Monitor Dashboard",
            "tags": ["network", "monitoring"],
            "timezone": "browser",
            "schemaVersion": 16,
            "version": 0,
            "panels": []
        },
        "overwrite": True
    }
    
    # Add Speedtest Latency Panel
    dashboard["dashboard"]["panels"].append({
        "title": "Speedtest Latency",
        "type": "graph",
        "datasource": "InfluxDB",
        "targets": [
            {"measurement": "speed_test", "select": [[{"params": ["ping"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["jitter"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_idle"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_download"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_upload"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_idle_high"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_download_high"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["latency_upload_high"], "type": "field"}]]}
        ],
        "yaxes": [{"format": "ms"}],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
    })
    
    # Add Speedtest Throughput Panel
    dashboard["dashboard"]["panels"].append({
        "title": "Speedtest Download/Upload",
        "type": "graph",
        "datasource": "InfluxDB",
        "targets": [
            {"measurement": "speed_test", "select": [[{"params": ["download"], "type": "field"}]]},
            {"measurement": "speed_test", "select": [[{"params": ["upload"], "type": "field"}]]}
        ],
        "yaxes": [{"format": "Mbps"}],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
    })
    
    # Add Buffer Bloat Panel
    dashboard["dashboard"]["panels"].append({
        "title": "Buffer Bloat",
        "type": "graph",
        "datasource": "InfluxDB",
        "targets": [
            {"measurement": "buffer_bloat", "select": [[{"params": ["min"], "type": "field"}]]},
            {"measurement": "buffer_bloat", "select": [[{"params": ["avg"], "type": "field"}]]},
            {"measurement": "buffer_bloat", "select": [[{"params": ["max"], "type": "field"}]]},
            {"measurement": "buffer_bloat", "select": [[{"params": ["mdev"], "type": "field"}]]}
        ],
        "yaxes": [{"format": "ms"}],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
    })
    
    # Save the dashboard configuration to a file
    with open('/home/pi/peeng/network_dashboard.json', 'w') as f:
        json.dump(dashboard, f)
    
    logging.info("Dashboard configuration saved to /home/pi/peeng/network_dashboard.json")
    logging.info("You can now import this dashboard in Grafana manually.")

def main():
    setup_grafana_dashboard()
    
    last_speed_test_time = 0
    last_buffer_bloat_test_time = 0
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

            # Run speed test every hour (3600 seconds)
            if current_time - last_speed_test_time >= 3600:
                speed = run_speed_test()
                if speed:
                    write_to_influxdb("speed_test", speed)
                    logging.info(f"Wrote speed test results to InfluxDB: {speed}")
                last_speed_test_time = current_time

            # Run buffer bloat test every hour (3600 seconds)
            if current_time - last_buffer_bloat_test_time >= 3600:
                buffer_bloat = measure_buffer_bloat()
                if buffer_bloat:
                    write_to_influxdb("buffer_bloat", buffer_bloat)
                    logging.info(f"Wrote buffer bloat results to InfluxDB: {buffer_bloat}")
                last_buffer_bloat_test_time = current_time

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")

        time.sleep(1)  # Wait for 1 second before the next measurement

if __name__ == "__main__":
    logging.info("Starting Enhanced Network Monitor")
    setup_grafana_dashboard()
    main()
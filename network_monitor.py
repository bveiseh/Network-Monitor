import subprocess
import time
from influxdb import InfluxDBClient
from datetime import datetime, timedelta
import logging
from collections import deque
import json
import requests
import re
import threading

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

# Ollama configuration
OLLAMA_URL = "http://100.100.58.42:9090/api/generate"
OLLAMA_MODEL = "llama3.1"

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

def setup_grafana_dashboard():
    logging.info("Grafana dashboard setup is not needed as the configuration is saved elsewhere.")
    pass

def get_last_hour_data():
    """Query InfluxDB for the last hour of data for all metrics."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    query_latency = f"""
    SELECT "min", "avg", "max", "mdev", "packet_loss"
    FROM "latency"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    """
    
    query_speed = f"""
    SELECT "download", "upload", "ping"
    FROM "speed_test"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    """
    
    query_latency_8888 = f"""
    SELECT "min", "avg", "max", "mdev", "packet_loss"
    FROM "latency_8.8.8.8"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    ORDER BY time DESC
    LIMIT 250
    """
    
    query_latency_1111 = f"""
    SELECT "min", "avg", "max", "mdev", "packet_loss"
    FROM "latency_1.1.1.1"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    ORDER BY time DESC
    LIMIT 250
    """
    
    latency_result = client.query(query_latency)
    speed_result = client.query(query_speed)
    latency_8888_result = client.query(query_latency_8888)
    latency_1111_result = client.query(query_latency_1111)
    
    latency_data = list(latency_result.get_points())
    speed_data = list(speed_result.get_points())
    latency_8888_data = list(latency_8888_result.get_points())
    latency_1111_data = list(latency_1111_result.get_points())
    
    # Calculate averages
    latency_avg = {
        'min': sum(point['min'] for point in latency_data) / len(latency_data) if latency_data else None,
        'avg': sum(point['avg'] for point in latency_data) / len(latency_data) if latency_data else None,
        'max': sum(point['max'] for point in latency_data) / len(latency_data) if latency_data else None,
        'mdev': sum(point['mdev'] for point in latency_data) / len(latency_data) if latency_data else None,
        'packet_loss': sum(point['packet_loss'] for point in latency_data) / len(latency_data) if latency_data else None
    }
    
    latency_avg_8888 = {
        'avg': sum(point['avg'] for point in latency_8888_data) / len(latency_8888_data) if latency_8888_data else None
    }
    
    latency_avg_1111 = {
        'avg': sum(point['avg'] for point in latency_1111_data) / len(latency_1111_data) if latency_1111_data else None
    }
    
    speed_avg = {
        'download': sum(point['download'] for point in speed_data) / len(speed_data) if speed_data else None,
        'upload': sum(point['upload'] for point in speed_data) / len(speed_data) if speed_data else None,
        'ping': sum(point['ping'] for point in speed_data) / len(speed_data) if speed_data else None
    }
    
    return {
        'latency_avg': latency_avg,
        'speed_avg': speed_avg,
        'latency_samples': latency_data[:10],  # Last 10 samples
        'speed_samples': speed_data[:3],  # Last 3 samples (assuming speed tests are less frequent)
        'latency_samples_8.8.8.8': latency_8888_data,  # Now includes up to 250 samples
        'latency_samples_1.1.1.1': latency_1111_data,  # Now includes up to 250 samples
        'latency_avg_8.8.8.8': latency_avg_8888,
        'latency_avg_1.1.1.1': latency_avg_1111
    }

def get_recent_data(minutes=15):
    """Query InfluxDB for the most recent data."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes)
    
    query_latency = f"""
    SELECT "min", "avg", "max", "mdev", "packet_loss"
    FROM "latency"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    """
    
    query_speed = f"""
    SELECT "download", "upload", "ping"
    FROM "speed_test"
    WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
    """
    
    latency_result = client.query(query_latency)
    speed_result = client.query(query_speed)
    
    return {
        'latency': list(latency_result.get_points()),
        'speed': list(speed_result.get_points())
    }

def generate_network_report(hourly_data, recent_data):
    """Generate a concise, narrative-driven network report using Ollama."""
    prompt = f"""
    Generate a brief, narrative-driven network health report based on the following data:

    Last Hour Averages:
    Latency:
    - Min: {hourly_data['latency_avg']['min']:.2f} ms
    - Avg: {hourly_data['latency_avg']['avg']:.2f} ms
    - Max: {hourly_data['latency_avg']['max']:.2f} ms
    - Mdev: {hourly_data['latency_avg']['mdev']:.2f} ms
    - Packet Loss: {hourly_data['latency_avg']['packet_loss']:.2f}%

    Speed:
    - Download: {hourly_data['speed_avg']['download']:.2f} Mbps
    - Upload: {hourly_data['speed_avg']['upload']:.2f} Mbps
    - Ping: {hourly_data['speed_avg']['ping']:.2f} ms

    Last 15 Minutes Data:
    Latency:
    {json.dumps(recent_data['latency'], indent=2)}

    Speed:
    {json.dumps(recent_data['speed'], indent=2)}

    Latency Comparison:
    Averages:
    - 8.8.8.8: {hourly_data['latency_avg_8.8.8.8']['avg']:.2f} ms
    - 1.1.1.1: {hourly_data['latency_avg_1.1.1.1']['avg']:.2f} ms

    Raw Data (last 250 samples):
    8.8.8.8: {json.dumps(hourly_data['latency_samples_8.8.8.8'], indent=2)}
    1.1.1.1: {json.dumps(hourly_data['latency_samples_1.1.1.1'], indent=2)}

    Rules:
    1. Provide a concise summary in exactly two to three sentences.
    2. Focus on the overall health and any significant deviations or trends based on the raw data and the averages.
    3. Use a conversational, but professional, clinical and very serious tone.
    4. Do not include technical jargon or specific numbers.
    5. Do not suggest improvements or mention buffer bloat.
    6. Look for any significant latency spike, speed drops, or packet loss. A few seconds of high latency or a sudden drop in speed is not relevant. look for sustained high latency or low speed.

    Your response should be brief and informative, suitable for a quick network health check by a non-technical user.
    """

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "max_tokens": 150
            }
        }, timeout=10)
        response.raise_for_status()
        
        report = response.json().get('response', '').strip()
        
        # Post-process the report
        sentences = report.split('.')
        if len(sentences) > 3:
            report = '. '.join(sentences[:3]) + '.'
        
        return report.strip()
    except requests.RequestException as e:
        logging.error(f"Error generating network report: {str(e)}")
        return "Network report unavailable due to a temporary issue."
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing Ollama response: {str(e)}")
        return "Unable to generate network report at this time."

def write_report_to_influxdb(report):
    """Write the generated report to InfluxDB."""
    current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    
    json_body = [
        {
            "measurement": "network_report",
            "tags": {
                "host": "raspberry_pi",
                "report_type": "latest"
            },
            "time": current_time,
            "fields": {
                "content": report
            }
        }
    ]
    
    success = client.write_points(json_body)
    
    if success:
        logging.info(f"Successfully wrote new report to InfluxDB: {report}")
    else:
        logging.error(f"Failed to write new report to InfluxDB: {report}")

def setup_data_retention_policy():
    client = InfluxDBClient(host='localhost', port=8086)
    
    # Create the database if it doesn't exist
    client.create_database(INFLUXDB_DATABASE)
    
    # Switch to the database
    client.switch_database(INFLUXDB_DATABASE)
    
    # Create the retention policy
    client.create_retention_policy(
        name='network_metrics_retention',
        duration='30d',
        replication='1',
        database=INFLUXDB_DATABASE,
        default=True
    )
    
    logging.info("Data retention policy set up successfully")

def purge_old_data():
    """Purge data older than 30 days from all measurements."""
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    measurements = ['latency', 'speed_test', 'buffer_bloat', 'network_report']
    
    for measurement in measurements:
        query = f'DELETE FROM "{measurement}" WHERE time < \'{thirty_days_ago}\''
        client.query(query)
    
    logging.info("Purged data older than 30 days from all measurements")

def main():
    setup_data_retention_policy()
    
    last_speed_test_time = 0
    last_report_time = 0
    last_purge_time = 0
    
    while True:
        try:
            current_time = int(time.time())
            
            # Measure and write latency for both targets (runs every second)
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
                logging.info("Starting hourly speed test")
                speed = run_speed_test()
                if speed:
                    write_to_influxdb("speed_test", speed)
                    logging.info(f"Wrote speed test results to InfluxDB: {speed}")
                last_speed_test_time = current_time
                logging.info("Completed hourly speed test")

            # Generate and write network report every 15 minutes
            if current_time - last_report_time >= 900:  # 900 seconds = 15 minutes
                logging.info("Generating new network report")
                hourly_data = get_last_hour_data()
                recent_data = get_recent_data(minutes=15)
                report = generate_network_report(hourly_data, recent_data)
                write_report_to_influxdb(report)
                last_report_time = current_time
            
            # Purge old data daily
            if current_time - last_purge_time >= 86400:  # 86400 seconds = 1 day
                purge_old_data()
                last_purge_time = current_time

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")
            logging.exception("Exception details:")  # This will log the full stack trace

        time.sleep(1)  # Wait for 1 second before the next measurement

if __name__ == "__main__":
    logging.info("Starting Enhanced Network Monitor with Speedtest Latency Metrics")
    client = InfluxDBClient(host='localhost', port=8086, database=INFLUXDB_DATABASE)
    main()
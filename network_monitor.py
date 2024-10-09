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
OLLAMA_MODEL = "llama3.1"  # Adjust this to the model you want to use

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

def get_last_two_hours_averages():
    """Query InfluxDB for the average values of all metrics over the last two hours."""
    query = """
    SELECT MEAN("min") as min, MEAN("avg") as avg, MEAN("max") as max, MEAN("mdev") as mdev, MEAN("packet_loss") as packet_loss
    FROM "latency"
    WHERE time > now() - 2h
    GROUP BY time(2h) fill(none)
    """
    latency_result = client.query(query)
    
    query = """
    SELECT MEAN("download") as download, MEAN("upload") as upload, MEAN("ping") as ping, MEAN("jitter") as jitter,
           MEAN("latency_idle") as latency_idle, MEAN("latency_download") as latency_download, MEAN("latency_upload") as latency_upload,
           MEAN("latency_idle_high") as latency_idle_high, MEAN("latency_download_high") as latency_download_high, MEAN("latency_upload_high") as latency_upload_high
    FROM "speed_test"
    WHERE time > now() - 2h
    GROUP BY time(2h) fill(none)
    """
    speed_result = client.query(query)
    
    # Combine results
    averages = {}
    for measurement, points in latency_result.items():
        averages['latency'] = next(points)
    for measurement, points in speed_result.items():
        averages['speed_test'] = next(points)
    
    return averages

def clean_report_text(text):
    """Clean up the report text by removing excessive newlines and formatting."""
    # Remove multiple consecutive newlines
    cleaned = re.sub(r'\n{2,}', '\n', text)
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    # Ensure single newline at the end
    cleaned = cleaned.rstrip('\n') + '\n'
    return cleaned

def get_last_two_hours_data():
    """Query InfluxDB for the last two hours of data for all metrics."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=2)
    
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
        'speed_test': list(speed_result.get_points())
    }

def generate_network_report(averages):
    """Generate a network report using Ollama."""
    # Fetch the last report from the database
    query = 'SELECT content, time FROM "network_report" WHERE "report_type" = \'latest\' ORDER BY time DESC LIMIT 1'
    result = client.query(query)
    previous_report = next(result.get_points(), None)

    # Get the last two hours of raw data
    last_two_hours_data = get_last_two_hours_data()

    prompt = f"""
    Generate a short, concise network report based on the following average metrics from the last two hours and raw data from the last two hours. Your response should be EXACTLY 2 sentences maximum, focusing only on significant deviations from the standards or notable performance of this network. Do not provide a separate summary.

    Rules:
    1. Highlight only metrics that are significantly outside the expected range.
    2. If all metrics are within expected ranges, provide a short statement confirming good network health.
    3. Be slightly humorous but professional.
    4. Do not read out statistics or numbers.
    5. Do not suggest improvements.
    6. Consider the previous report for trends, but only mention them if there's a significant change or continuation of a concerning trend.
    7. Look for trends in the data over time, like many moderate ping spikes. One or two extreme readings of any metric can be attributed to normal network fluctuations and should not be highlighted.
    8. If there are no significant trends or changes from the previous report, focus solely on the current network state.
    9. Focus only on latency, speed, and packet loss.
    10. Do not mention buffer bloat. It is not a concern. Never mention it.
    11. Average expected latencies are within 50ms of the normal speed test ping. If you are seeing spikes above 60ms, that is a concern and should be highlighted.

    Remember, you are an AI monitoring Brandon's home network. Keep your analysis extremely brief - this is just a quick summary of network health.

    Two-hour averages:
    Latency:
    - Min: {averages['latency']['min']:.2f} ms
    - Avg: {averages['latency']['avg']:.2f} ms
    - Max: {averages['latency']['max']:.2f} ms
    - Mdev: {averages['latency']['mdev']:.2f} ms
    - Packet Loss: {averages['latency']['packet_loss']:.2f}%

    Speed Test:
    - Download: {averages['speed_test']['download']:.2f} Mbps
    - Upload: {averages['speed_test']['upload']:.2f} Mbps
    - Ping: {averages['speed_test']['ping']:.2f} ms

    Raw data from the last two hours (up to 100 data points for each metric):
    Latency:
    {json.dumps(last_two_hours_data['latency'][:100], indent=2)}

    Speed Test:
    {json.dumps([{k: v for k, v in d.items() if k in ['download', 'upload', 'ping']} for d in last_two_hours_data['speed_test'][:100]], indent=2)}

    Average ISP Speeds:
    - Download: 930Mbps
    - Upload: 40Mbps
    - Ping: 20ms
    These are maximum speeds, actual speeds may be in the range of 75% of those speeds at any given time.
    
    Previous report:
    {previous_report['content'] if previous_report else "No previous report available."}

    IMPORTANT: Your response MUST be exactly two sentences long. Do not include any additional explanations, recommendations, or summaries beyond these two sentences. Focus solely on the most significant network health insights related to latency, speed, and packet loss, mentioning trends only if they are significant and ongoing.
    """

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "max_tokens": 100  # Limit the response length
            }
        })
        response.raise_for_status()
        
        report = response.json().get('response', '').strip()
        return clean_report_text(report)
    except requests.RequestException as e:
        logging.error(f"Error generating network report: {str(e)}")
        return "Unable to generate network report due to an error."
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing Ollama response: {str(e)}")
        return "Unable to parse the network report response."

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
    
    # Write the new report
    client.write_points(json_body)

    logging.info(f"Wrote new report to InfluxDB")

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
                averages = get_last_two_hours_averages()
                report = generate_network_report(averages)
                write_report_to_influxdb(report)
                logging.info(f"Generated and wrote network report to InfluxDB:\n{report}")
                last_report_time = current_time

            # Purge old data daily
            if current_time - last_purge_time >= 86400:  # 86400 seconds = 1 day
                purge_old_data()
                last_purge_time = current_time

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")

        time.sleep(1)  # Wait for 1 second before the next measurement

if __name__ == "__main__":
    logging.info("Starting Enhanced Network Monitor with Speedtest Latency Metrics")
    client = InfluxDBClient(host='localhost', port=8086, database=INFLUXDB_DATABASE)
    main()
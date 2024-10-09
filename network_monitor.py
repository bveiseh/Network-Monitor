import subprocess
import time
from influxdb import InfluxDBClient
from datetime import datetime
import logging
from collections import deque
import json

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
        # Use the new Speedtest CLI command format
        output = subprocess.check_output(['speedtest', '-f', 'json'], universal_newlines=True)
        result = json.loads(output)
        return {
            'download': result['download']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'upload': result['upload']['bandwidth'] * 8 / 1_000_000,  # Convert to Mbps
            'ping': result['ping']['latency']
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
    if measurement.startswith('latency'):
        latency_deque.append(fields)
        avg_fields = {
            'min': calculate_moving_average([d['min'] for d in latency_deque]),
            'avg': calculate_moving_average([d['avg'] for d in latency_deque]),
            'max': calculate_moving_average([d['max'] for d in latency_deque]),
            'mdev': calculate_moving_average([d['mdev'] for d in latency_deque]),
            'packet_loss': calculate_moving_average([d['packet_loss'] for d in latency_deque])
        }
        fields = avg_fields
    elif measurement == 'speed_test':
        speed_deque.append(fields)
        avg_fields = {
            'download': calculate_moving_average([d['download'] for d in speed_deque]),
            'upload': calculate_moving_average([d['upload'] for d in speed_deque]),
            'ping': calculate_moving_average([d['ping'] for d in speed_deque])
        }
        fields = avg_fields

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

def main():
    last_speed_test_time = 0
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

            # Run speed test every 5 minutes (300 seconds)
            if current_time - last_speed_test_time >= 300:
                speed = run_speed_test()
                if speed:
                    write_to_influxdb("speed_test", speed)
                    logging.info(f"Wrote speed test results to InfluxDB: {speed}")
                last_speed_test_time = current_time

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")

        time.sleep(1)  # Wait for 1 second before the next measurement

if __name__ == "__main__":
    logging.info("Starting Enhanced Network Monitor")
    main()

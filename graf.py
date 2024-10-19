import time
import requests
import json
import os

GRAFANA_URL = "http://localhost:3000"
API_KEY = "glsa_DS6Nia7aNSoM6hoaodHSHcPnSnZdHXTz_5fc69961"
DASHBOARD_UID = "fe0atovlm7o5cd"
JSON_FILE_PATH = "/home/pi/Network-Monitor/netdash.json"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

last_modified = 0

def create_or_update_dashboard(dashboard_json):
    payload = {
        "dashboard": dashboard_json,
        "overwrite": True
    }
    
    response = requests.post(f"{GRAFANA_URL}/api/dashboards/db", headers=headers, json=payload)
    
    if response.status_code == 200:
        print("Dashboard created/updated successfully")
    else:
        print(f"Failed to create/update dashboard: {response.text}")
        print(f"Response status code: {response.status_code}")
        print(f"Payload sent: {json.dumps(payload, indent=2)}")

def check_dashboard_exists():
    response = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}", headers=headers)
    if response.status_code == 200:
        print("Dashboard found")
        return True
    elif response.status_code == 404:
        print("Dashboard not found")
        return False
    else:
        print(f"Unexpected response when checking dashboard: {response.text}")
        return False

while True:
    current_modified = os.path.getmtime(JSON_FILE_PATH)
    if current_modified > last_modified:
        with open(JSON_FILE_PATH, 'r') as file:
            dashboard_json = json.load(file)
        
        dashboard_exists = check_dashboard_exists()
        
        if not dashboard_exists:
            print("Creating a new dashboard")
            # Ensure the dashboard JSON has the correct UID
            dashboard_json["uid"] = DASHBOARD_UID
            # Make sure the dashboard has a title
        
        create_or_update_dashboard(dashboard_json)
        
        last_modified = current_modified
    
    time.sleep(5)  # Check every 5 seconds

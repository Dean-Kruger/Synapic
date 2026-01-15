
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Load config to get credentials
config_path = Path(r"C:\Users\deank\.synapic_v2_config.json")
with open(config_path) as f:
    config = json.load(f)

base_url = config['datasource']['daminion_url']
user = config['datasource']['daminion_user']
passwd = config['datasource']['daminion_pass']

def probe():
    # Login
    login_url = f"{base_url}/api/UserManager/Login"
    data = json.dumps({"userName": user, "password": passwd}).encode('utf-8')
    req = urllib.request.Request(login_url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    
    with urllib.request.urlopen(req) as resp:
        cookies = resp.headers.get('Set-Cookie')
        print(f"Login success. Cookies: {cookies[:50]}...")

    # Probe Search
    # Use exact URL user suggested
    search_term = "cticc"
    query = f"5000,{search_term}"
    ops = "5000,all"
    
    # Try multiple lengths
    for length in [1, 5, 500]:
        endpoint = f"/api/MediaItems/Get?query={urllib.parse.quote(query)}&operators={urllib.parse.quote(ops)}&start=0&length={length}"
        url = f"{base_url}{endpoint}"
        print(f"\nProbing URL: {url}")
        
        req = urllib.request.Request(url)
        req.add_header('Cookie', cookies)
        
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            print(f"Response ({len(body)} bytes): {body}")
            try:
                data = json.loads(body)
                items = data.get('mediaItems', [])
                count = data.get('totalCount', 0)
                print(f"TotalCount: {count}, Items in list: {len(items)}")
                if items:
                    print(f"First item keys: {list(items[0].keys())}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")

if __name__ == "__main__":
    probe()

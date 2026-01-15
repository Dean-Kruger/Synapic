
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
        print(f"Login successful.")

    # Terms to try
    # 'adderley' was provided by user
    for term in ["adderley", "cticc"]:
        print(f"\n--- Testing term: {term} ---")
        query = f"5000,{term}"
        ops = "5000,all"
        
        params = urllib.parse.urlencode({
            "query": query,
            "operators": ops,
            "start": 0,
            "length": 5
        })
        url = f"{base_url}/api/MediaItems/Get?{params}"
        print(f"URL: {url}")
        
        req = urllib.request.Request(url)
        req.add_header('Cookie', cookies)
        
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode('utf-8')
                print(f"Raw Body ({len(body)} bytes): {body}")
                data = json.loads(body)
                print(f"Keys: {list(data.keys())}")
                count = data.get('totalCount', 0)
                items = data.get('mediaItems') or data.get('MediaItems') or data.get('items') or []
                print(f"totalCount: {count}, items found: {len(items)}")
        except Exception as e:
            print(f"Failed: {e}")

    # One more test without operators
    print(f"\n--- Testing without operators ---")
    url = f"{base_url}/api/MediaItems/Get?query=5000,adderley&start=0&length=5"
    req = urllib.request.Request(url)
    req.add_header('Cookie', cookies)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            print(f"Raw Body: {body}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    probe()

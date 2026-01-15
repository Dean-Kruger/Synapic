
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
    results = []
    
    # Login
    login_url = f"{base_url}/api/UserManager/Login"
    params = urllib.parse.urlencode({"userName": user, "password": passwd})
    req = urllib.request.Request(f"{login_url}?{params}", method='POST')
    
    with urllib.request.urlopen(req) as resp:
        cookies = resp.headers.get('Set-Cookie')
        results.append(f"Login success. Cookies found.")

    # Search for 'adderley'
    term = "adderley"
    query = f"5000,{term}"
    ops = "5000,all"
    params = urllib.parse.urlencode({
        "query": query,
        "operators": ops,
        "start": 0,
        "length": 1
    })
    url = f"{base_url}/api/MediaItems/Get?{params}"
    results.append(f"Probing: {url}")
    
    req = urllib.request.Request(url)
    req.add_header('Cookie', cookies)
    
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            results.append(f"Body: {body}")
    except Exception as e:
        results.append(f"Error: {e}")

    with open("probe_final.txt", "w") as f:
        f.write("\n".join(results))

if __name__ == "__main__":
    probe()

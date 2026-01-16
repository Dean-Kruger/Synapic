import requests
import json

def discover():
    host = "http://researchserver.juicefilm.local"
    prefixes = ["", "/daminion", "/api"]
    methods = ["params", "json"]
    endpoints = ["api/UserManager/Login", "api/Login"]
    
    username = "admin"
    password = "admin"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest'
    }

    for prefix in prefixes:
        for endpoint in endpoints:
            url = f"{host}{prefix}/{endpoint}"
            print(f"\n--- Testing URL: {url} ---")
            
            for method in methods:
                session = requests.Session()
                session.headers.update(headers)
                try:
                    if method == "params":
                        r = session.post(url, params={'userName': username, 'password': password}, timeout=5)
                    else:
                        r = session.post(url, json={'userName': username, 'password': password}, timeout=5)
                    
                    print(f"  Method {method}: Status {r.status_code}")
                    if r.status_code == 200:
                        print("  SUCCESS!")
                        # Try to get item count to verify session
                        r2 = session.get(f"{host}{prefix}/api/MediaItems/GetCount")
                        print(f"  Verify GetCount: {r2.status_code}")
                        if r2.status_code == 200:
                            print("  SESSION VERIFIED!")
                except Exception as e:
                    print(f"  Error: {e}")

if __name__ == "__main__":
    discover()

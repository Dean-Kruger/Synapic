import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def probe_daminion():
    base_urls = [
        "http://researchserver.juicefilm.local/daminion",
        "http://researchserver.juicefilm.local",
        "http://researchserver.juicefilm.local/daminion/api/v1",
        "http://researchserver.juicefilm.local/api"
    ]
    
    endpoints = [
        "api/UserManager/Login",
        "api/MediaItems/GetCount",
        "api/SharedCollection/GetCollections",
        "api/Settings/GetTags"
    ]
    
    username = "admin"
    password = "admin"
    
    for base in base_urls:
        print(f"\n--- Probing Base: {base} ---")
        session = requests.Session()
        
        # Try login first
        login_url = f"{base.rstrip('/')}/api/UserManager/Login"
        params = {'userName': username, 'password': password}
        try:
            print(f"Trying Login: {login_url}")
            r = session.post(login_url, params=params, timeout=5)
            print(f"Response: {r.status_code}")
            if r.status_code == 200:
                print("SUCCESS at this base URL!")
                # Probe other endpoints with this session
                for ep in endpoints[1:]:
                    url = f"{base.rstrip('/')}/{ep}"
                    r2 = session.get(url, timeout=5)
                    print(f"Probe {ep}: {r2.status_code}")
                continue
        except Exception as e:
            print(f"Error at {login_url}: {e}")

if __name__ == "__main__":
    probe_daminion()

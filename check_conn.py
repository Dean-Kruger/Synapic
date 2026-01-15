
import urllib.request
import logging

logging.basicConfig(level=logging.INFO)
url = "http://researchserver.juicefilm.local/daminion"
try:
    logging.info(f"Checking {url}")
    with urllib.request.urlopen(url, timeout=5) as response:
        logging.info(f"Status: {response.status}")
except Exception as e:
    logging.error(f"Error: {e}")

import sys
import os

# Add src to sys.path to allow importing DaminionAPI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.utils.daminion_api import DaminionAPI, DaminionAPIError

def test_live_api():
    base_url = "http://researchserver.juicefilm.local/daminion"
    username = "admin"
    password = "admin"

    print(f"Connecting to {base_url} as {username}...")
    api = DaminionAPI(base_url, username, password)

    try:
        # Step 1: Authenticate
        if api.authenticate():
            print("Successfully authenticated!")
        else:
            print("Authentication failed.")
            return

        # Step 2: Get total count of media items
        count_data = api.get_media_item_count()
        count = count_data.get('data', 0) if isinstance(count_data, dict) else count_data
        print(f"Total media items in catalog: {count}")

        # Step 3: Get Tags (Confirmed working via probe)
        print("Fetching tags...")
        # api/Settings/GetTags
        tags = api._request("GET", "api/Settings/GetTags")
        if tags:
            tag_list = tags.get('data') or tags
            print(f"Found {len(tag_list)} tags.")
            for tag in tag_list[:3]:
                print(f" - {tag.get('name') or tag.get('Title')}")

        # Step 4: Get Users
        print("Fetching users...")
        users = api.get_users()
        if users:
            print(f"Found {len(users)} users.")
            for user in users[:3]:
                print(f" - {user.get('userName') or user.get('Name')}")

    except DaminionAPIError as e:
        print(f"Daminion API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_live_api()

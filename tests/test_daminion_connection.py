r"""
Live connection test for Daminion server.

Credentials are stored in Windows Registry at:
  HKEY_CURRENT_USER\SOFTWARE\Synapic\Daminion

Run with --save to store credentials:
  python tests/test_daminion_connection.py --save

Run without arguments to test connection:
  python tests/test_daminion_connection.py
"""
import sys
import os
import logging
import argparse

# Ensure project root is in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging - default to WARNING for clean output
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def save_credentials():
    """Save Daminion credentials to registry."""
    from src.utils.registry_config import save_daminion_credentials
    
    # Default values - these match the test setup
    url = "http://damserver.local/daminion"
    username = "admin"
    password = "admin"
    
    print("\n" + "=" * 60)
    print("SAVE DAMINION CREDENTIALS TO REGISTRY")
    print("=" * 60)
    print(f"\nDefault values:")
    print(f"  URL:      {url}")
    print(f"  Username: {username}")
    print(f"  Password: {'*' * len(password)}")
    
    # Allow custom input
    custom = input("\nUse these defaults? [Y/n]: ").strip().lower()
    if custom == 'n':
        url = input(f"Server URL [{url}]: ").strip() or url
        username = input(f"Username [{username}]: ").strip() or username
        password = input(f"Password [{password}]: ").strip() or password
    
    if save_daminion_credentials(url, username, password):
        print("\n[OK] Credentials saved to Windows Registry!")
        print("     Location: HKEY_CURRENT_USER\\SOFTWARE\\Synapic\\Daminion")
    else:
        print("\n[FAIL] Failed to save credentials")
        return False
    
    return True


def test_connection():
    """Test connection to Daminion server using registry credentials."""
    from src.utils.registry_config import load_daminion_credentials, credentials_exist
    from src.core.daminion_client import DaminionClient, DaminionAPIError
    
    print("\n" + "=" * 60)
    print("DAMINION CONNECTION TEST")
    print("=" * 60)
    
    # Check for credentials
    if not credentials_exist():
        print("\n[FAIL] No Daminion credentials found in registry.")
        print("       Run with --save to store credentials first:")
        print("       python tests/test_daminion_connection.py --save")
        return False
    
    creds = load_daminion_credentials()
    if not creds:
        print("\n[FAIL] Failed to load credentials from registry.")
        return False
    
    print(f"\n  Server URL: {creds['url']}")
    print(f"  Username:   {creds['username']}")
    print(f"  Password:   {'*' * len(creds['password'])}")
    print("-" * 60)
    
    try:
        logger.info("Creating Daminion client...")
        client = DaminionClient(
            base_url=creds['url'],
            username=creds['username'],
            password=creds['password']
        )
        
        logger.info("Attempting authentication...")
        success = client.authenticate()
        
        if success:
            print("\n" + "=" * 60)
            print("[OK] CONNECTION SUCCESSFUL!")
            print("=" * 60)
            
            # Try to get item count
            try:
                count = client.get_total_count()
                print(f"\n  Total items in catalog: {count:,}")
            except Exception as e:
                logger.warning(f"Could not get item count: {e}")
            
            # Try to get shared collections
            try:
                collections = client.get_shared_collections()
                count = len(collections) if collections else 0
                print(f"  Shared collections: {count}")
                if collections:
                    for i, col in enumerate(collections[:5], 1):
                        name = col.get('name') or col.get('Name') or col.get('title') or 'Unnamed'
                        print(f"    {i}. {name}")
                    if len(collections) > 5:
                        print(f"    ... and {len(collections) - 5} more")
            except Exception as e:
                logger.warning(f"Could not get shared collections: {e}")
            
            return True
        else:
            print("\n[FAIL] Authentication returned False")
            return False
            
    except DaminionAPIError as e:
        print(f"\n[FAIL] API Error: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] Connection failed: {e}")
        logger.exception("Connection error details:")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Daminion server connection")
    parser.add_argument('--save', action='store_true', help='Save credentials to registry')
    parser.add_argument('--delete', action='store_true', help='Delete stored credentials')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.delete:
        from src.utils.registry_config import delete_daminion_credentials
        if delete_daminion_credentials():
            print("[OK] Credentials deleted from registry")
        else:
            print("[FAIL] Failed to delete credentials")
        return
    
    if args.save:
        save_credentials()
        print("\nNow testing connection...")
    
    success = test_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

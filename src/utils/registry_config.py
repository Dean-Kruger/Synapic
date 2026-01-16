"""
Windows Registry-based credential storage for Synapic.

Stores sensitive credentials (URLs, usernames, passwords) in the Windows Registry
to keep them out of version control.
"""
import winreg
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Registry path for Synapic credentials
REGISTRY_KEY = r"SOFTWARE\Synapic"
DAMINION_SUBKEY = r"SOFTWARE\Synapic\Daminion"


def _get_or_create_key(key_path: str) -> winreg.HKEYType:
    """Get or create a registry key."""
    try:
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
    except FileNotFoundError:
        return winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)


def save_daminion_credentials(url: str, username: str, password: str) -> bool:
    """
    Save Daminion credentials to Windows Registry.
    
    Args:
        url: Daminion server URL (e.g., http://damserver.local/daminion)
        username: Daminion username
        password: Daminion password
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        with _get_or_create_key(DAMINION_SUBKEY) as key:
            winreg.SetValueEx(key, "URL", 0, winreg.REG_SZ, url)
            winreg.SetValueEx(key, "Username", 0, winreg.REG_SZ, username)
            winreg.SetValueEx(key, "Password", 0, winreg.REG_SZ, password)
        
        logger.info(f"Saved Daminion credentials to registry for {url}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save Daminion credentials to registry: {e}")
        return False


def load_daminion_credentials() -> Optional[Dict[str, str]]:
    """
    Load Daminion credentials from Windows Registry.
    
    Returns:
        Dictionary with 'url', 'username', 'password' keys, or None if not found
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DAMINION_SUBKEY, 0, winreg.KEY_READ) as key:
            url, _ = winreg.QueryValueEx(key, "URL")
            username, _ = winreg.QueryValueEx(key, "Username")
            password, _ = winreg.QueryValueEx(key, "Password")
            
        return {
            "url": url,
            "username": username,
            "password": password
        }
        
    except FileNotFoundError:
        logger.debug("No Daminion credentials found in registry")
        return None
    except Exception as e:
        logger.error(f"Failed to load Daminion credentials from registry: {e}")
        return None


def delete_daminion_credentials() -> bool:
    """
    Delete Daminion credentials from Windows Registry.
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, DAMINION_SUBKEY)
        logger.info("Deleted Daminion credentials from registry")
        return True
    except FileNotFoundError:
        logger.debug("No Daminion credentials to delete")
        return True
    except Exception as e:
        logger.error(f"Failed to delete Daminion credentials from registry: {e}")
        return False


def credentials_exist() -> bool:
    """Check if Daminion credentials exist in the registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DAMINION_SUBKEY, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False

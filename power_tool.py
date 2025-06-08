# power_tool.py - The single, unified, and guaranteed Python tool for all operations.

import requests
import json
import os
import sys
import pyotp  # Dependency for generating TOTP tokens
from datetime import datetime, timedelta

# --- For better terminal output ---
class Colors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_success(message):
    print(f"{Colors.OKGREEN}✅ Success: {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.FAIL}❌ Error: {message}{Colors.ENDC}", file=sys.stderr)
    sys.exit(1)

def get_env_vars(required_vars):
    """Fetches and validates required environment variables."""
    config = {}
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        print_error(f"Missing required environment variables: {', '.join(missing_vars)}")
    for var in required_vars:
        config[var] = os.environ.get(var)
    return config

def api_request(method, url, headers, data=None):
    """Central function for making API requests with robust error handling."""
    try:
        response = requests.request(
            method, url, headers=headers,
            data=json.dumps(data) if data else None,
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        reason = e.response.reason
        try:
            server_error = e.response.json().get('error', e.response.text)
            print_error(f"API Error: HTTP {status} {reason}\n> Server Message: {server_error}")
        except json.JSONDecodeError:
            print_error(f"API Error: HTTP {status} {reason}\n> Non-JSON Response: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print_error(f"Network Error: Failed to connect to the API.\n> Details: {e}")

# --- Action Functions ---
def add_or_update_user(config):
    print(f"🔄 Preparing to add/update user: '{config['USER_ID']}'...")
    expires_at = datetime.now() + timedelta(days=int(config['EXPIRE_DAYS']))
    payload = {
        "id": config['USER_ID'],
        "name": config.get('USER_NAME') or config['USER_ID'],
        "expires_at": int(expires_at.timestamp()),
        "data_limit_bytes": int(config['DATA_LIMIT_GB']) * (1024**3),
        "config_source": config['CONFIG_SOURCE']
    }
    result = api_request("POST", f"{config['WORKER_URL']}/api/users", config['HEADERS'], payload)
    print_success(result.get('message'))
    print(f"🔗 {Colors.BOLD}Subscription Link:{Colors.ENDC} {result.get('subscription_link')}")

def get_user_info(config):
    print(f"🔎 Getting information for user: '{config['USER_ID']}'...")
    result = api_request("GET", f"{config['WORKER_URL']}/api/users/{config['USER_ID']}", config['HEADERS'])
    user = result['user']
    print_success(f"User '{user['id']}' found.")

    # Prettify output
    for key in ['created_at', 'updated_at', 'expires_at']:
        if user.get(key):
            user[key] = f"{datetime.fromtimestamp(user[key]).strftime('%Y-%m-%d %H:%M:%S')} (UTC)"
    user['data_limit_gb'] = round(user.get('data_limit_bytes', 0) / (1024**3), 2)
    user['used_traffic_gb'] = round(user.get('used_traffic_bytes', 0) / (1024**3), 2)
    del user['data_limit_bytes']
    del user['used_traffic_bytes']

    print(json.dumps(user, indent=2))

def deactivate_user(config):
    print(f"⛔ Preparing to deactivate user: '{config['USER_ID']}'...")
    result = api_request("DELETE", f"{config['WORKER_URL']}/api/users/{config['USER_ID']}", config['HEADERS'])
    print_success(result.get('message'))

def main():
    """Main entry point and router for the application."""
    base_vars = ['WORKER_URL', 'TOTP_SECRET_KEY', 'ACTION']
    env_config = get_env_vars(base_vars)

    # --- Generate the time-sensitive token ---
    try:
        # 5-minute interval to match the Cloudflare Worker settings
        totp = pyotp.TOTP(env_config['TOTP_SECRET_KEY'], interval=300) 
        current_token = totp.now()
    except Exception as e:
        print_error(f"Could not generate TOTP token. Is TOTP_SECRET_KEY a valid Base32 string? Error: {e}")

    env_config['HEADERS'] = {
        "Authorization": f"Bearer {current_token}",
        "Content-Type": "application/json"
    }

    action = env_config['ACTION']

    # --- Route to the correct function ---
    if action == 'add_or_update':
        required = ['USER_ID', 'EXPIRE_DAYS', 'DATA_LIMIT_GB', 'CONFIG_SOURCE']
        env_config.update(get_env_vars(required))
        add_or_update_user(env_config)
    elif action == 'get_info':
        env_config.update(get_env_vars(['USER_ID']))
        get_user_info(env_config)
    elif action == 'deactivate':
        env_config.update(get_env_vars(['USER_ID']))
        deactivate_user(env_config)
    else:
        print_error(f"Invalid action: '{action}'. Must be 'add_or_update', 'get_info', or 'deactivate'.")

if __name__ == '__main__':
    main()

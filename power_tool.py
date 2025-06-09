# filename: power_tool.py
import requests
import json
import os
import sys
import pyotp
from datetime import datetime, timedelta

# --- Configuration and Error Handling ---
try:
    WORKER_URL = os.environ['WORKER_URL']
    TOTP_SECRET = os.environ['TOTP_SECRET_KEY']
    ACTION = os.environ['ACTION']
except KeyError as e:
    print(f"❌ Error: Missing required environment variable from GitHub Secrets: {e}", file=sys.stderr)
    sys.exit(1)

try:
    # The TOTP interval must match the one in the worker (default 300s / 5 min)
    totp = pyotp.TOTP(TOTP_SECRET, interval=300)
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {totp.now()}"
    }
except Exception as e:
    print(f"❌ Error: Could not generate TOTP token. Is TOTP_SECRET_KEY a valid Base32 string? Details: {e}", file=sys.stderr)
    sys.exit(1)


# --- API Communication ---
def api_request(method, endpoint, data=None):
    try:
        response = requests.request(method, f"{WORKER_URL.rstrip('/')}{endpoint}", headers=HEADERS, json=data, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error: {e.response.status_code} {e.response.reason}\nServer Response:\n{e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

# --- Main Actions ---
def add_update_user():
    days = int(os.environ['EXPIRE_DAYS'])
    gb = int(os.environ['DATA_LIMIT_GB'])
    payload = {
        "id": os.environ['USER_ID'],
        "name": os.environ.get('USER_NAME') or os.environ['USER_ID'],
        "expires_at": int((datetime.now() + timedelta(days=days)).timestamp()),
        "data_limit_bytes": str(gb * 1024**3), # Send as string to match BigInt
        "config_source": os.environ['CONFIG_SOURCE']
    }
    result = api_request("POST", "/api/users", payload)
    print(f"✅ {result.get('message')}")
    print(f"🔗 Subscription Link: {result.get('subscription_link')}")

def get_user_info():
    user_id = os.environ['USER_ID']
    result = api_request("GET", f"/api/users/{user_id}")
    print("✅ User info retrieved successfully:")
    print(json.dumps(result.get('user'), indent=2, ensure_ascii=False))

def deactivate_user():
    user_id = os.environ['USER_ID']
    result = api_request("DELETE", f"/api/users/{user_id}")
    print(f"✅ {result.get('message')}")

# --- Main Execution ---
if __name__ == "__main__":
    print(f"🚀 Executing action: '{ACTION}'...")
    if ACTION == 'add_or_update': add_update_user()
    elif ACTION == 'get_info': get_user_info()
    elif ACTION == 'deactivate': deactivate_user()
    else:
        print(f"❌ Invalid action: '{ACTION}'", file=sys.stderr)
        sys.exit(1)


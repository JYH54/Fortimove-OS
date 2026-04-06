import os
import json
import urllib.request
import urllib.error

env_vars = {}
with open('/home/fortymove/Fortimove-OS/image-localization-system/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip()

print("--- Testing Anthropic API Models ---")
api_key = env_vars.get('ANTHROPIC_API_KEY')

models_to_test = [
    "claude-3-haiku-20240307",
    "claude-3-sonnet-20240229",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest"
]

url = "https://api.anthropic.com/v1/messages"
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
    "anthropic-dangerous-direct-browser-access": "true"
}

for model in models_to_test:
    data = {
        "model": model,
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Hello"}]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            print(f"[{model}] Success! (Status: {response.getcode()})")
    except urllib.error.HTTPError as e:
        print(f"[{model}] Failed (HTTP {e.code}): {json.loads(e.read().decode()).get('error', {}).get('message')}")
    except Exception as e:
        print(f"[{model}] Error: {e}")

import smtplib
import json
import urllib.request
import urllib.error
import ssl

env_vars = {}
with open('/home/fortymove/Fortimove-OS/image-localization-system/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip()

print("--- Testing Anthropic API ---")
api_key = env_vars.get('ANTHROPIC_API_KEY')
print(f"API Key present: {'Yes' if api_key else 'No'}")

url = "https://api.anthropic.com/v1/messages"
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}
data = {
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Hello"}]
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print("Success!")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")

print("\n--- Testing Google SMTP ---")
email = env_vars.get('SCOUT_EMAIL_SENDER')
password = env_vars.get('SCOUT_EMAIL_PASSWORD')
print(f"Email: {email}")

try:
    context = ssl.create_default_context()
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls(context=context)
    server.ehlo()
    server.login(email, password)
    print("SMTP Login Successful!")
    server.quit()
except Exception as e:
    print(f"SMTP Error: {e}")

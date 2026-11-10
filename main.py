import os
from dotenv import load_dotenv
import httpx

def load_config():
    load_dotenv()
    config = {
        "api_url": os.getenv("PRISM_API_URL"),
        "client_id": os.getenv("PRISM_CLIENT_ID"),
        "client_secret": os.getenv("PRISM_CLIENT_SECRET")
    }
    if not all(config.values()):
        raise ValueError("Missing configuration values in .env file")
    return config

def authenticate(config):
    url = config["api_url"]
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    try:
        response = httpx.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP/API failure: {e}")
        return None
    except httpx.RequestError as e:
        print(f"Network/connection failure: {e}")
        return None

def main():
    config = load_config()
    token_response = authenticate(config)
    if token_response:
        if "access_token" in token_response:
            print("Successful authentication")
        else:
            print("Authentication failure")
    else:
        print("Authentication failure")

if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv
import httpx
import sys

def load_config():
    load_dotenv()
    config = {
        "api_url": os.getenv("PRISM_API_BASE_URL"),
        "token_url": os.getenv("PRISM_TOKEN_URL"),
        "client_id": os.getenv("PRISM_CLIENT_ID"),
        "client_secret": os.getenv("PRISM_CLIENT_SECRET")
    }
    if not all(config.values()):
        raise ValueError("Missing configuration values in .env file")
    return config

def authenticate(config):
    url = config["token_url"]
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "rhipeapi"
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

def search_customers(search_text=None):
    config = load_config()

    token_response = authenticate(config)

    if not token_response or "access_token" not in token_response:
        print("Authentication failure")
        return

    url = f"{config['api_url']}/api/v2/me/customers"

    headers = {
        "Authorization": f"Bearer {token_response['access_token']}",
        "Accept": "application/json"
    }

    all_customers = []
    page = 1
    page_size = 10
    total_records = None

    try:
        with httpx.Client(timeout=30.0) as client:

            while True:
                params = {
                    "page": page,
                    "pageSize": page_size,
                    "activeCustomers": "true"
                }

                response = client.get(
                    url,
                    headers=headers,
                    params=params
                )

                response.raise_for_status()
                result = response.json()

                customers = result.get("Items", [])
                total_records = result.get("TotalRecords")

                if not isinstance(customers, list):
                    raise ValueError("Unexpected customer response format")

                print(
                    f"Page {page}: retrieved {len(customers)} customers"
                )

                all_customers.extend(customers)

                # Stop when the API returns no more customers.
                if not customers:
                    break

                # Stop when we've retrieved all reported records.
                if (
                    total_records is not None
                    and len(all_customers) >= total_records
                ):
                    break

                # Stop if the final page is smaller than page_size.
                if len(customers) < page_size:
                    break

                page += 1

        print()
        print(f"Total customers retrieved: {len(all_customers)}")

        # Apply optional local name filtering.
        if search_text:
            matching_customers = [
                customer
                for customer in all_customers
                if search_text.lower()
                in (customer.get("CustomerName") or "").lower()
            ]
        else:
            matching_customers = all_customers

        print(f"Matching customers: {len(matching_customers)}")
        print()

        for customer in matching_customers:
            print(
                f"Customer ID: {customer.get('CustomerId')}, "
                f"Name: {customer.get('CustomerName')}"
            )

    except httpx.HTTPStatusError as e:
        print(f"HTTP failure: {e}")

        if e.response.status_code == 401:
            print("Authentication failed or token rejected")
        elif e.response.status_code == 403:
            print("Access forbidden")
        elif e.response.status_code == 400:
            print("Invalid API request")

    except httpx.RequestError as e:
        print(f"Network/connection failure: {e}")

    except (ValueError, TypeError) as e:
        print(f"Invalid API response: {e}")
def main():
    search_text = sys.argv[1] if len(sys.argv) > 1 else None
    search_customers(search_text)    




if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv
import httpx

class PrismClient:
    def __init__(self):
        load_dotenv()
        self.config = {
            "api_url": os.getenv("PRISM_API_BASE_URL"),
            "token_url": os.getenv("PRISM_TOKEN_URL"),
            "client_id": os.getenv("PRISM_CLIENT_ID"),
            "client_secret": os.getenv("PRISM_CLIENT_SECRET")
        }
        if not all(self.config.values()):
            raise ValueError("Missing configuration values in .env file")
        self.access_token = self.authenticate()

    def authenticate(self):
        url = self.config["token_url"]
        client_id = self.config["client_id"]
        client_secret = self.config["client_secret"]
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
            return response.json().get("access_token")
        except httpx.HTTPStatusError as e:
            print(f"HTTP/API failure: {e}")
            return None
        except httpx.RequestError as e:
            print(f"Network/connection failure: {e}")
            return None

    def search_customers(self, search_text=None):
        url = f"{self.config['api_url']}/api/v2/me/customers"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        all_customers = []
        page = 1
        page_size = 10
        total_records = None

        while True:
            params = {
                "page": page,
                "pageSize": page_size,
                "activeCustomers": "true"
            }

            response = httpx.get(
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

            all_customers.extend(customers)

            if not customers:
                break

            if total_records is not None and len(all_customers) >= total_records:
                break

            if len(customers) < page_size:
                break

            page += 1

        if search_text:
            matching_customers = [
                customer
                for customer in all_customers
                if search_text.lower() in (customer.get("CustomerName") or "").lower()
            ]
        else:
            matching_customers = all_customers

        return matching_customers

    def list_microsoft_csp_subscriptions(self, customer_id: str):
        url = f"{self.config['api_url']}/api/v2/microsoftcsp/tenants"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        all_subscriptions = []
        page = 1
        page_size = 50
        total_records = None

        while True:
            params = {
                "endCustomerId": customer_id,
                "page": page,
                "pageSize": page_size
            }

            response = httpx.get(
                url,
                headers=headers,
                params=params
            )

            response.raise_for_status()
            result = response.json()

            tenants = result.get("Items", [])
            total_records = result.get("TotalRecords")

            if not isinstance(tenants, list):
                raise ValueError("Unexpected tenant response format")

            for tenant in tenants:
                tenant_id = tenant.get("TenantId")
                tenant_domain = tenant.get("TenantDomain")
                subscription_url = f"{self.config['api_url']}/api/v2/microsoftcsp/tenants/{tenant_id}/subscriptions"
                subscription_params = {
                    "status": "Active"
                }
                subscription_response = httpx.get(
                    subscription_url,
                    headers=headers,
                    params=subscription_params
                )
                subscription_response.raise_for_status()
                subscription_result = subscription_response.json()
                subscriptions = subscription_result
                for subscription in subscriptions:
                    all_subscriptions.append({
                        "CustomerId": customer_id,
                        "TenantId": tenant_id,
                        "TenantDomain": tenant_domain,
                        "SubscriptionId": subscription.get("SubscriptionId"),
                        "SubscriptionFriendlyName": subscription.get("SubscriptionFriendlyName")
                    })

            if not tenants:
                break

            if total_records is not None and len(all_subscriptions) >= total_records:
                break

            if len(tenants) < page_size:
                break

            page += 1

        return all_subscriptions

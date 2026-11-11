import sys
from prism_client import PrismClient

def main():
    search_text = sys.argv[1] if len(sys.argv) > 1 else None
    prism_client = PrismClient()
    customers = prism_client.search_customers(search_text)
    for customer in customers:
        print(f"Customer ID: {customer.get('CustomerId')}, Name: {customer.get('CustomerName')}")

if __name__ == "__main__":
    main()

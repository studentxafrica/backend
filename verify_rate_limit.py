import requests
import time

BASE_URL = "http://localhost:5000/api/v1/auth/check-email"


def verify_rate_limit():
    print(f"Testing rate limit on {BASE_URL}")

    # 1. Warm up / check success (should return 200)
    for i in range(5):
        try:
            response = requests.post(
                BASE_URL, json={"email": f"test{i}@example.com"})
            print(f"Request {i+1}: Status {response.status_code}")
            if response.status_code != 200:
                print(f"FAILED: Expected 200, got {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"FAILED: Request {i+1} exception: {e}")

    # 2. This request should trigger rate limit (429)
    try:
        response = requests.post(BASE_URL, json={"email": "limit@example.com"})
        print(f"Request 6 (should fail): Status {response.status_code}")
        if response.status_code == 429:
            print("SUCCESS: Rate limit triggered (429 Too Many Requests)")
        else:
            print(f"FAILED: Expected 429, got {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"FAILED: Request 6 exception: {e}")


if __name__ == "__main__":
    verify_rate_limit()

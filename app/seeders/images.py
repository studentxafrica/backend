import requests
from bs4 import BeautifulSoup

query = "student+discounts+coupons+offers+deals+university+college+students"
url = f"https://www.bing.com/images/search?q={query}"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

image_links = []
for img_tag in soup.find_all("img"):
    src = img_tag.get("src")
    if src and "http" in src:
        image_links.append(src)



import requests # type: ignore
from random import randint

PEXELS_API_KEY="asa6uFY8eneFhwaumnBtTpmQU3xOcnEhcTvl53ooThvqRhTgbmkKPi8i"
def get_random_pexels_image(query: str = "student discounts") -> str:
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        f"https://api.pexels.com/v1/search?query={query}&per_page=1&page={randint(1, 10)}&orientation=landscape",
        headers=headers
    )
    if response.status_code == 200:
        photos = response.json().get("photos", [])
        if photos:
            return photos[0]['src']['medium']
    return "https://via.placeholder.com/100"

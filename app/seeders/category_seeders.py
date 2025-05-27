from app.models.category import Category
from faker import Faker
from . import get_random_pexels_image

fake = Faker()

#  Category Seeder with realistic data
categories = [
    {
        "name": "Fashion",
        "slug": "fashion",
    },
    {
        "name": "Food & Drink",
        "slug": "food-drink",
    },
    {
        "name": "Travel",
        "slug": "travel",
    },
    {
        "name": "Health & Beauty",
        "slug": "health-beauty",
    },
    {
        "name": "Electronics & Tech",
        "slug": "electronics-tech",
    },
    {
        "name": "Home & Accessories",
        "slug": "home-accessories",
    },
    {
        "name": "Sports & Outdoors",
        "slug": "sports-outdoors",
    },
    {
        "name": "Education",
        "slug": "education",
    },
    {
        "name": "Entertainment",
        "slug": "entertainment",
    }
]


def seed_categories():
    """
    Seed the database with sample categories.
    """
    for category in categories:
        category_instance = Category(**category)
        category_instance.save()


print("Category seeder completed successfully.")

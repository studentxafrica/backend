from app import app
import click
from typing import List

# CLI command to run seeders

@app.cli.command("count-offers")
def count_offers():
    """
    Count the number of offers in the database.
    """
    from app.models.offer import Offer
    from app.models.merchant import Merchant
    from app.models.category import Category
    from app import db
    categories: List[Category] = db.session.query(Category).all()
    for category in categories:
        category.offer_count = db.session.query(Offer).join(Merchant).filter(Merchant.category_id == category.id).count()
        category.merchant_count = len(category.merchants)
        category.save()
    print(f"Merchant and Offer counts updated for {len(categories)} categories.")

@app.cli.command("seed")
@click.option("--students", type=int, help="Seed students.")
@click.option("--merchants", type=int, help="Seed merchants.")
@click.option("--categories", is_flag=True, help="Seed categories.")
@click.option("--offers", type=int, help="Seed offers.")
def seed(students, merchants, categories, offers):
    """
    Seed the database with sample data.
    """
    if offers:
        from app.seeders.offer_seeder import seed_offers
        seed_offers(offers)
        print("Offer seeder completed successfully.")

    if students:
        from app.seeders.student_seeders import seed_students
        seed_students(students)
        print("Student seeder completed successfully.")

    if merchants:
        if merchants == -1:
            from app.seeders.merchant_seeder import edit_merchants
            edit_merchants()
            print("Merchants updated successfully.")
            return
        from app.seeders.merchant_seeder import seed_merchants
        seed_merchants(merchants)
        print("Merchant seeder completed successfully.")

    if categories:
        from app.seeders.category_seeders import seed_categories
        seed_categories()
        print("Category seeder completed successfully.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)

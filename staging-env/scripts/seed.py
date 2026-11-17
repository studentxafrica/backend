"""
Create the staging schema and the accounts the tests use.

Run inside the api container (scripts/up.sh does this):

    python staging-env/scripts/seed.py

The schema comes from the models with create_all(), because the migrations in
production's checkout only alter tables that already exist. Re-running is safe.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from run import app  # noqa: E402
from app import db
from app.models import Category, Merchant
from app.models.admin import Administrator, AdminRole
from app.seeders.category_seeders import categories, seed_categories

ADMIN_USERNAME = "staging-admin"
MERCHANT_EMAIL = "shopzetu@staging.invalid"


def main():
    admin_password = os.environ["STAGING_ADMIN_PASSWORD"]
    merchant_password = os.environ["STAGING_MERCHANT_PASSWORD"]

    with app.app_context():
        db.create_all()

        if not db.session.query(Category).first():
            seed_categories()
        category = db.session.query(Category).filter_by(slug=categories[0]["slug"]).first()

        admin = db.session.query(Administrator).filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            admin = Administrator(
                username=ADMIN_USERNAME, email="admin@staging.invalid",
                first_name="Staging", last_name="Admin",
                role=AdminRole.SUPER_ADMIN, is_superuser=True,
            )
        admin.password = admin_password
        admin.save()

        merchant = db.session.query(Merchant).filter_by(email=MERCHANT_EMAIL).first()
        if not merchant:
            merchant = Merchant(email=MERCHANT_EMAIL, name="ShopZetu (staging)")
        merchant.password = merchant_password
        merchant.category_id = category.id if category else None
        merchant.email_verified_on = merchant.email_verified_on or datetime.now(timezone.utc)
        merchant.approved_on = merchant.approved_on or datetime.now(timezone.utc)
        merchant.save()

        print(f"seeded: admin '{ADMIN_USERNAME}', approved merchant {MERCHANT_EMAIL}, "
              f"{db.session.query(Category).count()} categories")


if __name__ == "__main__":
    main()

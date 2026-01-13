from app import create_app, db, jwt_manager, file_handler
import click
import os
import dotenv
from flask.cli import AppGroup
from typing import List

# Load .flaskenv if it exists
dotenv.load_dotenv('.flaskenv')

app = create_app(os.environ.get('FLASK_ENV') or 'default')
app.logger.info(
    f"Starting application in {os.environ.get('FLASK_ENV') or 'default'} mode."
)


@app.context_processor
def inject_globals():
    """ 
    Inject global variables into templates.
    """
    import datetime
    return {
        "frontend_url": app.config.get("FRONTEND_URL", "http://localhost:2211"),
        "backend_url": app.config.get("BACKEND_URL", "http://localhost:4000"),
        "app_name": app.config.get("APP_NAME", "StudentX"),
        "current_year": datetime.datetime.now().year
    }


@app.teardown_appcontext
def shutdown_session(exception=None):
    """
    Close the database session after each request.
    """
    if exception:
        app.logger.error(f"Exception during request: {exception}")
        db.session.rollback()
    db.session.remove()


@jwt_manager.user_lookup_loader
def load_user(jwt_header, jwt_payload):
    """
    Load user from JWT token.
    """
    from app.models import Administrator, Consumer, Merchant
    from sqlalchemy import or_

    user_id = jwt_payload['sub']
    user_type = jwt_payload.get('user_type')  # Add user_type to JWT claims
    
    # If user_type is in token, query directly
    if user_type == 'consumer':
        return db.session.query(Consumer).filter_by(id=user_id).first()
    elif user_type == 'merchant':
        return db.session.query(Merchant).filter_by(id=user_id).first()
    elif user_type == 'admin':
        return db.session.query(Administrator).filter_by(id=user_id).first()
    
    # Fallback: single query with UNION (still better than 3 separate queries)
    user = db.session.query(Consumer).filter_by(id=user_id).first()
    if user:
        return user
    user = db.session.query(Merchant).filter_by(id=user_id).first()
    if user:
        return user
    return db.session.query(Administrator).filter_by(id=user_id).first()

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
        category.offer_count = db.session.query(Offer).join(
            Merchant).filter(Merchant.category_id == category.id).count()
        category.merchant_count = len(category.merchants)
        category.save()
    print(
        f"Merchant and Offer counts updated for {len(categories)} categories.")


@app.cli.command("app")
@click.option("--expire-offers", is_flag=True, help="Expire offers that are past their end date.")
@click.option("--console", is_flag=True, help="Create an admin user.")
def expire_offers(expire_offers, console):
    """
    Expire offers that are past their end date.
    """
    if expire_offers:
        app.logger.info("CLI: Expiring offers that are past their end date...")
        from app.func_util.expire_offers import update_status as update_status_func
        update_status_func()
        app.logger.info("CLI: Expired offers successfully.")
    if console:
        from console import AdminConsole
        app.config['FLASK_DEBUG'] = False
        console = AdminConsole()
        console.cmdloop()


@app.cli.command("seed")
@click.option("--students", type=int, help="Seed students.")
@click.option("--merchants", type=int, help="Seed merchants.")
@click.option("--categories", is_flag=True, help="Seed categories.")
@click.option("--offers", type=int, help="Seed offers.")
@click.option("--edit-offers", is_flag=True, help="Edit offers. Options: cover_image, start_date, end_date, highlighted_until, featured_until.")
@click.option("--coupons", type=int, help="Seed coupons")
@click.option("--qrcodes", is_flag=True, help="Edit coupons.")
def seed(students, merchants, categories, offers, coupons, edit_offers, qrcodes):
    """
    Seed the database with sample data.
    """
    if qrcodes:
        from app import db
        from app.models import Coupon
        coupon_list: list[Coupon] = db.session.query(Coupon).all()
        for coupon in coupon_list:
            coupon._generate_qr_code()
            coupon.save()
    if edit_offers:
        from app.seeders.offer_seeder import edit_offers as edit_offers_func, generate_coupon_title_desc
        from app.models.offer import Offer
        # edit_offers_func(edit_offers)
        from app import db
        offers: list[Offer] = db.session.query(Offer).all()
        for offer in offers:
            generate_coupon_title_desc(offer)
        print("Offer edit completed successfully.")
        return
    if offers:
        from app.seeders.offer_seeder import seed_offers
        seed_offers(offers)
        print("Offer seeder completed successfully.")

    if coupons:
        if coupons == -1:
            from app.seeders.coupon_seeders import edit_coupons
            edit_coupons()
            print("Coupons updated successfully.")
            return
        from app.seeders.coupon_seeders import seed_coupons
        seed_coupons(coupons)
        print("Coupon seeder completed successfully.")

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
    app.run(host="0.0.0.0", port=4000, use_reloader=False)

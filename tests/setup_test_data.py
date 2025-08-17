import os
import sys
from datetime import datetime, timezone, timedelta
import random

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Now we can import from app
from app import app, db
from app.models import Offer, Category, Store

def setup_test_data():
    """Set up test data for connection timeout testing"""
    with app.app_context():
        # Create test categories
        categories = [
            Category(name='Food & Dining', slug='food-dining'),
            Category(name='Shopping', slug='shopping'),
            Category(name='Entertainment', slug='entertainment')
        ]
        for category in categories:
            db.session.add(category)
        db.session.commit()

        # Create test stores
        stores = [
            Store(name='Test Store 1', slug='test-store-1'),
            Store(name='Test Store 2', slug='test-store-2'),
            Store(name='Test Store 3', slug='test-store-3')
        ]
        for store in stores:
            db.session.add(store)
        db.session.commit()

        # Create test offers
        current_time = datetime.now(timezone.utc)
        for i in range(100):  # Create 100 test offers
            featured_until = current_time + timedelta(days=random.randint(1, 30))
            offer = Offer(
                title=f'Test Offer {i}',
                description=f'Description for test offer {i}',
                merchant_id=random.choice(stores).id,
                category_id=random.choice(categories).id,
                status='active',
                featured_until=featured_until,
                start_date=current_time,
                end_date=current_time + timedelta(days=60)
            )
            db.session.add(offer)
        
        db.session.commit()
        print("Test data setup complete!")

if __name__ == '__main__':
    setup_test_data() 
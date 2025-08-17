import os
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
import random
from flask import current_app

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Now we can import from app
from app import app, db
from app.models import Offer

# Create Flask app
app.config.update({
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': 'mysql+pymysql://root:root@localhost/studentxdev',
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'pool_size': 5,
        'pool_timeout': 5,
        'pool_recycle': 3600,
        'connect_args': {
            'connect_timeout': 2,
            'read_timeout': 2,
            'write_timeout': 2
        }
    }
})

def simulate_connection_timeout():
    """Simulate conditions that could cause connection timeout"""
    
    with app.app_context():
        # 1. Create multiple concurrent connections
        def long_running_query():
            try:
                # Simulate a long-running query
                current_time = datetime.now(timezone.utc)
                offers = db.session.query(Offer).filter(
                    Offer.featured_until > current_time,
                    Offer.status == 'active'
                ).order_by(Offer.featured_until.desc()).all()
                
                # Simulate processing time
                time.sleep(30)  # Sleep for 30 seconds
                
                return len(offers)
            except Exception as e:
                print(f"Query failed: {str(e)}")
                return 0

        # 2. Create multiple threads to simulate concurrent users
        threads = []
        for i in range(20):  # Create 20 concurrent connections
            thread = threading.Thread(target=long_running_query)
            threads.append(thread)
            thread.start()
            time.sleep(0.5)  # Small delay between thread starts

        # 3. Wait for all threads to complete
        for thread in threads:
            thread.join()

def simulate_slow_network():
    """Simulate slow network conditions"""
    with app.app_context():
        # Modify MySQL connection to simulate slow network
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'pool_timeout': 5,
            'pool_recycle': 3600,
            'connect_args': {
                'connect_timeout': 2,
                'read_timeout': 2,
                'write_timeout': 2
            }
        }
        
        # Force connection pool to be recreated
        db.engine.dispose()
        
        # Run queries that might timeout
        try:
            current_time = datetime.now(timezone.utc)
            offers = db.session.query(Offer).filter(
                Offer.featured_until > current_time,
                Offer.status == 'active'
            ).order_by(Offer.featured_until.desc()).all()
            print(f"Found {len(offers)} offers")
        except Exception as e:
            print(f"Query failed with slow network: {str(e)}")

def simulate_high_load():
    """Simulate high database load"""
    with app.app_context():
        def generate_load():
            while True:
                try:
                    # Randomly query different parts of the database
                    if random.random() < 0.3:
                        # Heavy query
                        current_time = datetime.now(timezone.utc)
                        offers = db.session.query(Offer).filter(
                            Offer.featured_until > current_time,
                            Offer.status == 'active'
                        ).order_by(Offer.featured_until.desc()).all()
                    else:
                        # Light query
                        db.session.query(Offer).limit(1).all()
                    
                    time.sleep(0.1)  # Small delay between queries
                except Exception as e:
                    print(f"Load test query failed: {str(e)}")
                    break

        # Start multiple threads to generate load
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=generate_load)
            thread.daemon = True  # Thread will be killed when main program exits
            threads.append(thread)
            thread.start()

        # Let the load run for 60 seconds
        time.sleep(60)

if __name__ == '__main__':
    # Run the simulations
    print("Testing connection timeout...")
    simulate_connection_timeout()
    
    print("\nTesting slow network conditions...")
    simulate_slow_network()
    
    print("\nTesting high load...")
    simulate_high_load() 
# Test auth views from the API
from app import create_app, db, file_handler
import os
import sys
import unittest
from flask import Flask

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)
print(project_root)


BASE_AUTH_URL = '/api/v1/auth'


class TestAuthViews(unittest.TestCase):
    def setUp(self):
        """Set up the Flask app and test client."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        """Clean up after each test."""
        with self.app.app_context():
            # Close the log file handler
            global file_handler
            if file_handler is not None:
                file_handler.close()
                file_handler = None

            # Remove the database session and drop all tables
            db.session.remove()
            db.drop_all()

    def test_register_consumer(self):
        """Test consumer registration."""

        # Test with valid data
        from random import randint
        response = self.client.post(f'{BASE_AUTH_URL}/user/consumer/register', json={
            'email': f'john.doe@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '123-456-7890',
            'school': 'Example University',
            'graduation_year': 2023,
            'major': 'Computer Science',
            'student_id': 'S123456',
            'location': 'City, Country',
            'bio': 'Just a test user.'
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn('username', response.json)
        self.assertEqual(response.json['username'], 'John')

        # Test with missing required fields
        response = self.client.post(f'{BASE_AUTH_URL}/user/consumer/register', json={
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '123-456-7890',
            'school': 'Example University',
            'graduation_year': 2023,
            'major': 'Computer Science',
            'student_id': 'S123456',
            'location': 'City, Country',
                        'bio': 'Just a test user.'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('message', response.json)
        self.assertEqual(response.json['message'], 'Missing email or password')

        # Test with existing email
        response = self.client.post(f'{BASE_AUTH_URL}/user/consumer/register', json={
            'email': 'john.doe@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '123-456-7890',
            'school': 'Example University',
            'graduation_year': 2023,
            'major': 'Computer Science',
            'student_id': 'S123456',
            'location': 'City, Country',
            'bio': 'Just a test user.'
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn('message', response.json)
        self.assertNotIn('data', response.json)
        self.assertEqual(response.json['message'], 'Email already exists')

    def test_login_consumer(self):
        """Test consumer login."""
        # First register a consumer
        self.client.post(f'{BASE_AUTH_URL}/user/consumer/register', json={
            'email': 'john.doe@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '123-456-7890',
            'school': 'Example University',
            'graduation_year': 2023,
            'major': 'Computer Science',
            'student_id': 'S123456',
            'location': 'City, Country',
            'bio': 'Just a test user.'
        })

        # Now test login
        response = self.client.post(f'{BASE_AUTH_URL}/user/login', json={
            'email': 'john.doe@example.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('user', response.json)
        self.assertEqual(response.json['user']['email'], 'john.doe@example.com')
        # Check if jwt token is present in Set-Cookie header
        self.assertIn('access_token', response.headers.get('Set-Cookie', ''))

        # Test login with invalid credentials
        response = self.client.post(f'{BASE_AUTH_URL}/user/login', json={
            'email': 'john.doe@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn('message', response.json)
        self.assertEqual(response.json['message'], 'Invalid email or password')

    def test_merchant_login(self):
        """Test merchant login."""
        # First register a merchant
        with self.app.app_context():
            merchant = {
                'email': 'studentx@evilcorp.com',
                'name': 'Example Corp',
                'password': 'password123',
                'phone': '123-456-7890',
                'city': 'City',
                'country': 'Country',
                'zip_code': '12345',
                'preferred_currency': 'USD',
            }
            from app.models.merchant import Merchant
            new_merchant = Merchant(**merchant)
            new_merchant.save()

        # Now test login
        response = self.client.post(f'{BASE_AUTH_URL}/merchant/login', json={
            'email': 'studentx@evilcorp.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('user', response.json)
        self.assertEqual(response.json['user']
                         ['email'], 'studentx@evilcorp.com')
        # Check if jwt token is present in cookies
        self.assertIn('access_token', response.headers.get('Set-Cookie', ''))


if __name__ == '__main__':
    unittest.main()

from app.models.consumer import Consumer
from faker import Faker
from app import db
from sqlalchemy.exc import IntegrityError # type: ignore

fake = Faker()

def seed_students(number: int = 5000):
    """
    Seed the database with sample students (consumers).
    """
    for _ in range(number):
        student = {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(safe=True),  # ensures uniqueness
            "password": "Pa$$word1",
            "school": fake.company(),
            "graduation_year": fake.year(),
            "major": fake.job(),
            "student_id": fake.unique.bothify(text='STU-####', letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
            "bio": fake.sentence(nb_words=10),
            "location": fake.city(),
            "phone": fake.phone_number(),
            "profile_picture": fake.image_url(width=100, height=100),
        }

        try:
            student_instance = Consumer(**student)
            db.session.add(student_instance)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


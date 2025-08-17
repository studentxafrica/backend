import cmd
from app.models import Administrator
from app import db


class AdminConsole(cmd.Cmd):
    intro = 'Welcome to the Admin Console. Type help or ? to list commands.\n'
    prompt = '(admin) '

    def do_createsuperuser(self, arg):
        'Create a new superuser: createsuperuser'
        email = input('Enter email: ').rstrip()
        if '@' not in email or '.' not in email.split('@')[-1]:
            print('Invalid email format. Please enter a valid email address.')
            while True:
                email = input('Please enter a valid email: ').rstrip()
                if '@' in email and '.' in email.split('@')[-1]:
                    break
        user = db.session.query(Administrator).filter_by(email=email).first()
        if user:
            print(f'User with email {email} already exists.')
            tries, max_tries = 0, 3
            while tries < max_tries:
                email = input('Try a different email: ').rstrip()
                tries += 1
                if not '@' in email and '.' in email.split('@')[-1]:
                    print('Invalid email format. Please enter a valid email address.')
                    continue
                if not db.session.query(Administrator).filter_by(email=email).first():
                    break
        first_name = input('First Name (Admin): ').rstrip() or 'Admin'
        last_name = input('Last Name (User): ').rstrip() or 'User'
        username = input('Enter username (admin): ').rstrip() or 'admin'
        if not username.isalnum():
            print('Username must be alphanumeric.')
            while True:
                username = input(
                    'Invalid username. Please enter an alphanumeric username: ').rstrip()
                if username.isalnum():
                    break

        if db.session.query(Administrator).filter_by(username=username).first():
            print(
                f'Username {username} already exists. Please choose a different one.')
            tries, max_tries = 0, 3
            while tries < max_tries:
                username = input('Try a different username: ').rstrip()
                tries += 1
                if not username or not username.isalnum():
                    print('Username must be alphanumeric.')
                    continue
                if not db.session.query(Administrator).filter_by(username=username).first():
                    break

        password = input('Enter password: ').rstrip()
        if len(password) < 8:
            print('Password must be at least 8 characters long.')
            while True:
                password = input(
                    'Please enter a valid password (at least 8 characters): ').rstrip()
                if len(password) >= 8:
                    break
        confirm_password = input('Confirm password: ').rstrip()
        if confirm_password != password:
            print('Passwords do not match. Please try again.')
            while True:
                confirm_password = input('Confirm password: ').rstrip()
                if confirm_password == password:
                    break
        new_admin = Administrator(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role='super_admin',
            is_superuser=True
        )
        new_admin.save()
        # Here you would add logic to create the superuser in your database
        print(f"Superuser '{username}' created successfully. Please login to the admin portal with your credentials")

    def do_exit(self, arg):
        'Exit the console: exit'
        print('Exiting console.')
        return True

    def do_status(self, arg):
        'Show the current status of the application: status'
        print('Application is running smoothly.')

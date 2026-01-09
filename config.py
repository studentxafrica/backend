import os
import dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv.load_dotenv(os.path.join(basedir, ".env"))

env_file = {
    'default': os.path.join(basedir, '.env'),
    'development': os.path.join(basedir, '.env.dev'),
    'production': os.path.join(basedir, '.env'),
    'testing': os.path.join(basedir, '.env.test')
}


def save_config_from_input(display_text, config_name):
    """
    Save a configuration setting to the .env file.
    """
    value = input(display_text).rstrip()
    os.environ[config_name] = value
    return value


class Config:
    """
    Configuration class for the StudentX application.
    """
    # Application configuration
    APP_NAME = "StudentX"
    SECRET_KEY = "TheQuickBrownFoxJumpedOverALazyDog$$1305"
    SECURITY_PASSWORD_SALT = "Stvd3ntXPa$$wordSa1T"

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://studentx.co.ke")
    BACKEND_URL = os.environ.get("BACKEND_URL", "https://api.studentx.co.ke")

    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = True  # Only if using HTTPS
    JWT_ACCESS_COOKIE_NAME = 'access_token'
    JWT_COOKIE_SAMESITE = 'None'
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_CSRF_HEADER_NAME = 'X-CSRF-Token'
    JWT_ACCESS_CSRF_FIELD_NAME = 'csrf_token'
    JWT_REFRESH_CSRF_HEADER_NAME = 'X-CSRF-Token'
    JWT_REFRESH_CSRF_FIELD_NAME = 'csrf_token'

    # Mail connection configuration options - Mailtrap SDK
    MAILTRAP_API_TOKEN = os.environ.get("MAILTRAP_API_TOKEN")

    # Mail Sender Settings
    MAIL_DEFAULT_SENDER_EMAIL = os.environ.get("MAIL_DEFAULT_SENDER_EMAIL", "info@studentx.co.ke")
    MAIL_DEFAULT_SENDER_NAME = os.environ.get("MAIL_DEFAULT_SENDER_NAME", "StudentX")

    # Administrator Mail Settings
    ADMINISTRATOR_SENDER = "Administrator <admin@studentx.co.ke>"
    ADMINISTRATOR_MAIL = os.environ.get(
        "ADMINISTRATOR_MAIL", "info@studentx.co.ke"
    )

    # Database configuration
    DB_HOST = os.environ.get('DB_HOST') or save_config_from_input(
        f"Enter your database host (default: localhost): ", 'DB_HOST') or "localhost"
    # Default values for database credentials
    DB_USER = os.environ.get('DB_USER') or save_config_from_input(
        f"Enter your database user (default: {APP_NAME.lower()}_dev_user): ", 'DB_USER') or f"{APP_NAME.lower()}_dev_user"
    # Default values for database password
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or save_config_from_input(
        f"Enter your database password (default: {APP_NAME.lower()}_dev_password): ", 'DB_PASSWORD') or f"{APP_NAME.lower()}_dev_password"
    DB_NAME = os.environ.get('DB_NAME') or save_config_from_input(
        f"Enter your database name (default: {APP_NAME.lower()}_dev): ", 'DB_NAME') or f"{APP_NAME.lower()}_dev"
    # Default port for MySQL
    DB_PORT = os.environ.get('DB_PORT') or save_config_from_input(
        f"Enter your database port (default: 3306): ", 'DB_PORT') or "3306"

    # SQLAlchemy engine options
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Optimal for most web apps (reduced from 10)
        'pool_size': 8,
        'pool_recycle': 300,         # 5 minutes (matches wait_timeout)
        'pool_pre_ping': True,       # Essential for stability
        'max_overflow': 8,           # Matches pool_size (reduced from 20)
        'pool_timeout': 10,          # Wait max 10 sec for connection
        'pool_use_lifo': True,       # Better performance for web apps
        'isolation_level': 'READ COMMITTED'  # Better performance than REPEATABLE READ
    }
    # The SQLAlchemy connection string.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-WTF flag for CSRF
    # CSRF_ENABLED = True


class DevelopmentConfig(Config):
    """
    Development configuration class.
    Inherits from Config and can override specific settings for development.
    """
    print("Loading DevelopmentConfig...")
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    SQLALCHEMY_ECHO = False  # Enable SQL query logging for debugging
    LOG_FILE = 'app_dev.log'
    LOG_FILE_MODE = 'w'

    @staticmethod
    def init_app(app):
        print("Initializing DevelopmentConfig...")
        if os.path.exists(env_file['development']):
            app.logger.info(
                f"Loading environment variables from {os.path.basename(env_file['development'])}.")
            dotenv.load_dotenv(env_file['development'])
        elif os.path.exists(env_file['default']):
            app.logger.warning(
                f"Development env file not found: {os.path.basename(env_file['development'])}. Defaulting to {os.path.basename(env_file['default'])}.")
            dotenv.load_dotenv(env_file['default'])
        else:
            app.logger.warning("No env file found. Using default settings.")
            dotenv.load_dotenv(env_file['default'])


class ProductionConfig(Config):
    """
    Production configuration class.
    Inherits from Config and can override specific settings for production.
    """
    print("Loading ProductionConfig...")
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    SQLALCHEMY_ECHO = False  # Disable SQL query logging in production
    LOG_FILE = 'app_prod.log'
    LOG_FILE_MODE = 'a'  # Append to log file in production

    @staticmethod
    def init_app(app):
        print("Initializing ProductionConfig...")
        if os.path.exists(env_file['production']):
            app.logger.info(
                f"Loading environment variables from {os.path.basename(env_file['production'])}.")
            dotenv.load_dotenv(env_file['production'])
        elif os.path.exists(env_file['default']):
            app.logger.warning(
                f"Production env file not found: {os.path.basename(env_file['production'])}. Defaulting to {os.path.basename(env_file['default'])}.")
            dotenv.load_dotenv(env_file['default'])
        else:
            app.logger.warning("No env file found. Using default settings.")
            dotenv.load_dotenv(env_file['default'])


class TestingConfig(Config):
    """
    Testing configuration class.
    Inherits from Config and can override specific settings for testing.
    """
    print("Loading TestingConfig...")
    TESTING = True
    # Use in-memory SQLite database for tests
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False  # Disable CSRF protection for testing
    LOG_FILE = 'app_test.log'
    LOG_FILE_MODE = 'w'  # Write to log file in testing mode

    def __init__(self):
        super().__init__()

    @staticmethod
    def init_app(app):
        """
        Initialize the application with testing-specific settings.
        """
        TestingConfig.TEST_DB_NAME = os.environ.get('TEST_DB_NAME') or save_config_from_input(
            f"Enter your test database name (default: {Config.APP_NAME.lower()}_test): ", 'TEST_DB_NAME') or f"{Config.APP_NAME.lower()}_test"

        # Default values for test database credentials
        TestingConfig.TEST_DB_USER = os.environ.get('TEST_DB_USER') or save_config_from_input(
            f"Enter your test database user (default: {Config.APP_NAME.lower()}_test_user): ", 'TEST_DB_USER') or f"{Config.APP_NAME.lower()}_test_user"
        TestingConfig.TEST_DB_PASSWORD = os.environ.get(
            'TEST_DB_PASSWORD') or save_config_from_input(
            f"Enter your test database password (default: {Config.APP_NAME.lower()}_test_password): ", 'TEST_DB_PASSWORD') or f"{Config.APP_NAME.lower()}_test_password"
        TestingConfig.TEST_DB_HOST = os.environ.get('TEST_DB_HOST') or save_config_from_input(
            f"Enter your test database host (default: localhost): ", 'TEST_DB_HOST') or "localhost"
        TestingConfig.TEST_DB_PORT = os.environ.get('TEST_DB_PORT') or save_config_from_input(
            f"Enter your test database port (default: 3306): ", 'TEST_DB_PORT') or "3306"
        TestingConfig.SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{TestingConfig.TEST_DB_USER}:{TestingConfig.TEST_DB_PASSWORD}@{TestingConfig.TEST_DB_HOST}:{TestingConfig.TEST_DB_PORT}/{TestingConfig.TEST_DB_NAME}' or \
            "sqlite:///:test-db"
        print("Initializing TestingConfig...")
        if os.path.exists(env_file['testing']):
            app.logger.info(
                f"Loading environment variables from {os.path.basename(env_file['testing'])}.")
            dotenv.load_dotenv(env_file['testing'])
        elif os.path.exists(env_file['default']):
            app.logger.warning(
                f"Testing env file not found: {os.path.basename(env_file['testing'])}. Defaulting to {os.path.basename(env_file['default'])}.")
            dotenv.load_dotenv(env_file['default'])
        else:
            app.logger.warning("No env file found. Using default settings.")
            dotenv.load_dotenv(env_file['default'])


config = {
    'default': DevelopmentConfig,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

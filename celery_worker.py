from app import create_app
from app.celery_app import celery, init_celery

app = create_app()
init_celery(app)

# Import tasks so Celery can discover them
import app.tasks.coupon_upload  # noqa: F401

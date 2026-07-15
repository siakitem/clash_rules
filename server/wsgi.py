from app import create_app
from settings import Settings


settings = Settings.from_env()
app = create_app(settings)

import os

class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'ltymub2026'
    
    # Лимиты
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_PERIOD = 60
    MAX_TEMPLATE_SIZE = 10
    
    # Пути
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMPLATES_STORAGE = os.path.join(BASE_DIR, 'templates_storage')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
    DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')
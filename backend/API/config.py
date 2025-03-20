import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///medical.db')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    MODEL_PATH = os.path.abspath(r"C:\Users\Nour Hesham\Downloads\AI-Disease-Classification\models\save_model\model_classification.h5")
    IMG_SIZE = (240, 240)
    
    # إعدادات تسجيل الدخول الاجتماعي
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    FACEBOOK_CLIENT_ID = os.getenv('FACEBOOK_CLIENT_ID')
    FACEBOOK_CLIENT_SECRET = os.getenv('FACEBOOK_CLIENT_SECRET')
    
    APPLE_CLIENT_ID = os.getenv('APPLE_CLIENT_ID')
    APPLE_CLIENT_SECRET = os.getenv('APPLE_CLIENT_SECRET')
    APPLE_TEAM_ID = os.getenv('APPLE_TEAM_ID')
    APPLE_KEY_ID = os.getenv('APPLE_KEY_ID')
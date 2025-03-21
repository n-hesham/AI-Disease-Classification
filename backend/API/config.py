import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من `.env`
load_dotenv()

class Config:
    # 🔑 إعدادات الأمان
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # 🛢️ إعدادات قاعدة البيانات
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///medical.db')

    # 🔍 مفتاح API لـ OpenAI (إن وجد)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

    # 🔹 إعدادات تسجيل الدخول الاجتماعي
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    FACEBOOK_CLIENT_ID = os.getenv('FACEBOOK_CLIENT_ID', '')
    FACEBOOK_CLIENT_SECRET = os.getenv('FACEBOOK_CLIENT_SECRET', '')

    APPLE_CLIENT_ID = os.getenv('APPLE_CLIENT_ID', '')
    APPLE_CLIENT_SECRET = os.getenv('APPLE_CLIENT_SECRET', '')
    APPLE_TEAM_ID = os.getenv('APPLE_TEAM_ID', '')
    APPLE_KEY_ID = os.getenv('APPLE_KEY_ID', '')

    # ✅ طباعة القيم للتحقق عند التشغيل
    @staticmethod
    def print_config():
        print(f"🔍 SECRET_KEY: {Config.SECRET_KEY[:5]}***")  # ✅ إخفاء المفتاح عند الطباعة
        print(f"🛢️ DATABASE_URL: {Config.SQLALCHEMY_DATABASE_URI}")
        print(f"🔹 GOOGLE_CLIENT_ID: {'SET' if Config.GOOGLE_CLIENT_ID else 'NOT SET'}")
        print(f"🔹 FACEBOOK_CLIENT_ID: {'SET' if Config.FACEBOOK_CLIENT_ID else 'NOT SET'}")
        print(f"🔹 APPLE_CLIENT_ID: {'SET' if Config.APPLE_CLIENT_ID else 'NOT SET'}")

# ✅ طباعة الإعدادات عند بدء التشغيل
Config.print_config()

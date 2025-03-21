import os
import joblib
from tensorflow.keras.models import load_model
from config import Config

# تخزين الموديل والمعلومات الخاصة به
model = None
class_names = {
    0: "Bacterial Pneumonia",
    1: "COVID-19",
    2: "Edema",
    3: "Lung Opacity",
    4: "Normal",
    5: "Tuberculosis",
    6: "Viral Pneumonia"
}

def load_ai_model():
    """تحميل الموديل عند تشغيل التطبيق (Lazy Loading)."""
    global model
    if model is None:  # ✅ تجنب إعادة التحميل
        print(f"🔍 Loading model from: {Config.MODEL_PATH}")
        try:
            if Config.MODEL_PATH.endswith('.pkl'):
                model = joblib.load(Config.MODEL_PATH)  # ✅ تحميل الموديل باستخدام `joblib`
            elif Config.MODEL_PATH.endswith('.h5'):
                model = load_model(Config.MODEL_PATH)  # ✅ تحميل الموديل باستخدام `Keras`
            else:
                raise ValueError("Unsupported model format! Use '.pkl' or '.h5'")

            print("✅ Model loaded successfully!")
            print(f"📌 Class Names: {class_names}")  # ✅ طباعة أسماء الفئات للتحقق

        except Exception as e:
            print(f"❌ Error loading model: {e}")
            model = None  # تجنب تعطل التطبيق إذا فشل التحميل

    return model

# ✅ تحميل الموديل عند بدء التشغيل
load_ai_model()

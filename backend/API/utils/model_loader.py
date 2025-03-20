from tensorflow.keras.models import load_model
from config import Config

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

try:
    model = load_model(Config.MODEL_PATH)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
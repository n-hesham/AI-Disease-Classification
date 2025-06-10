import cv2
import numpy as np
from PIL import Image

def apply_disease_specific_enhancement(image, disease_type):
    """Applies light disease-specific enhancement."""
    if disease_type == 'Edema':
        blurred = cv2.GaussianBlur(image, (3, 3), 0)
        return cv2.addWeighted(image, 1.2, blurred, -0.2, 0)

    elif disease_type == 'Lung_Opacity':
        return cv2.convertScaleAbs(image, alpha=1.1, beta=3)

    elif disease_type == 'Tuberculosis':
        kernel = np.array([[0, -1, 0], [-1, 5.5, -1], [0, -1, 0]])
        return cv2.filter2D(image, -1, kernel)

    elif disease_type == 'Corona_Virus_Disease':
        return cv2.bilateralFilter(image, d=7, sigmaColor=50, sigmaSpace=50)

    elif disease_type == 'Bacterial_Pneumonia':
        kernel = np.ones((2, 2), np.uint8)
        closed = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
        return cv2.convertScaleAbs(closed, alpha=1.05, beta=5)

    elif disease_type == 'Viral_Pneumonia':
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        return cv2.filter2D(image, -1, kernel)

    # No enhancement for unknown/normal
    return image


def enhance_medical_image(image, disease_type=None, img_size=(224, 224)):
    """
    Enhances chest X-ray images with soft processing and disease-specific adjustment.

    Parameters:
    - image (numpy.ndarray): Input image (RGB or grayscale).
    - disease_type (str): Optional disease type to guide enhancement.
    - img_size (tuple): Target size (height, width).

    Returns:
    - numpy.ndarray: Enhanced image.
    """
    # Step 1: Convert to grayscale if image is RGB
    is_rgb = (len(image.shape) == 3 and image.shape[2] == 3)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if is_rgb else image.copy()

    # Step 2: Resize image
    resized = cv2.resize(gray, img_size, interpolation=cv2.INTER_AREA).astype(np.uint8)

    # Step 3: Apply CLAHE (soft contrast enhancement)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    contrast_enhanced = clahe.apply(resized)

    # Step 4: Apply mild denoising
    denoised = cv2.fastNlMeansDenoising(contrast_enhanced, None, h=5, templateWindowSize=7, searchWindowSize=21)

    # Step 5: Apply disease-specific enhancement (if applicable)
    enhanced = apply_disease_specific_enhancement(denoised, disease_type)

    # Step 6: Normalize image to 0–255
    enhanced = cv2.normalize(enhanced, None, 0, 255, cv2.NORM_MINMAX)

    # Step 7: Return to RGB if original image was RGB
    if is_rgb:
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)

    return enhanced

def preprocess_image(img):
    img = enhance_medical_image(img, disease_type=None, img_size=(224,224)) 
    img = img.astype(np.float32) / 255.0 
    return img


def allowed_file(filename):
    """Checks if uploaded file is of allowed type."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

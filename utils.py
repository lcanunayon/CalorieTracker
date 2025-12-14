import os
import io
import math
import requests
from PIL import Image, ImageStat


# expanded mapping from food keywords to approximate calories per serving
CALORIE_MAP = {
    'apple': 95,
    'banana': 105,
    'pizza': 285,
    'cheeseburger': 303,
    'hamburger': 303,
    'hotdog': 150,
    'ice_cream': 207,
    'cake': 350,
    'sandwich': 250,
    'salad': 150,
    'french_fries': 312,
    'spaghetti': 420,
    'sushi': 200,
    'steak': 679,
    'egg': 78,
    'bacon': 43,
    'bagel': 245,
    'bread': 79,
    'cookie': 160,
    'doughnut': 195,
    'rice': 240,
    'noodle': 350,
    'pasta': 400,
    'fried_rice': 450,
    'curry': 420,
    'enchilada': 500,
}


def _label_from_filename(filename: str):
    if not filename:
        return None
    name = os.path.splitext(os.path.basename(filename))[0].lower()
    tokens = [t for part in name.replace('-', ' ').replace('_', ' ').split() for t in [part] ]
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        for k in CALORIE_MAP:
            if k in t or t in k:
                return k
    return None


def _area_proportion(image: Image.Image):
    # Estimate proportion of image area that is non-background (food)
    # Convert to grayscale and threshold by brightness to ignore background
    try:
        small = image.convert('L').resize((128, 128))
        stat = ImageStat.Stat(small)
        mean = stat.mean[0]
        # create a simple threshold using mean brightness
        bw = small.point(lambda p: 0 if abs(p - mean) < 18 else 255)
        pixels = bw.getdata()
        food_pixels = sum(1 for p in pixels if p == 0)
        return food_pixels / (128 * 128)
    except Exception:
        return 0.15


def _call_hf_inference(image_path: str):
    """Call Hugging Face Inference API (image-classification) if HF_API_KEY provided.

    Returns list of (label, score) tuples or None on failure.
    """
    api_key = os.environ.get('HF_API_KEY') or os.environ.get('HUGGINGFACE_API_KEY')
    if not api_key:
        return None
    # recommended model for image classification
    model = os.environ.get('HF_MODEL', 'google/vit-base-patch16-224')
    url = f'https://api-inference.huggingface.co/models/{model}'
    headers = { 'Authorization': f'Bearer {api_key}' }
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
        resp = requests.post(url, headers=headers, data=data, timeout=20)
        if resp.status_code != 200:
            return None
        j = resp.json()
        # HF returns list of {label:...,score:...} for image-classification
        results = []
        if isinstance(j, list):
            for item in j:
                lbl = item.get('label') or item.get('class')
                score = float(item.get('score', 0))
                results.append((lbl, score))
            return results
    except Exception:
        return None
    return None


def estimate_calories(image_path):
    """Estimate food label and calories from an image.

    Returns: (label, calories_estimate, confidence)

    Behavior:
    - If `HF_API_KEY` is set in the environment, call Hugging Face image-classification
      model and use the top label to map to a calorie estimate.
    - Otherwise, use filename heuristics and a simple area-based portion-size multiplier.
    """
    # 1) Try Hugging Face inference if available
    hf = _call_hf_inference(image_path)
    if hf:
        top_label, top_score = hf[0]
        # normalize label text
        key = top_label.lower().replace(' ', '_')
        # map known labels
        for k in CALORIE_MAP:
            if k in key or key in k:
                base = CALORIE_MAP[k]
                # try to scale by confidence (rough)
                est = int(round(base * (0.9 + 0.6 * min(1.0, top_score))))
                return top_label, est, float(top_score)
        # fallback: return top label with default
        return top_label, 300, float(top_score)

    # 2) Filename-based quick match
    filename = os.path.basename(image_path) if image_path else ''
    label_key = _label_from_filename(filename)
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception:
        img = None

    if label_key:
        base = CALORIE_MAP.get(label_key, 250)
        # if we have the image, try to scale by area proportion
        if img:
            prop = _area_proportion(img)
            if prop > 0.25:
                mult = 1.6
            elif prop > 0.12:
                mult = 1.1
            else:
                mult = 0.8
            est = int(round(base * mult))
            return label_key, est, 0.75
        return label_key, base, 0.7

    # 3) If no filename match, use image area heuristic to guess portion size
    if img:
        # compute dominant color heuristic (yellow-ish -> banana)
        stat = ImageStat.Stat(img.resize((64,64)))
        r,g,b = stat.mean
        prop = _area_proportion(img)
        # guess food type by color intensity
        if r > 120 and g > 110 and b < 100:
            label = 'banana'
            base = CALORIE_MAP.get('banana', 105)
        else:
            label = 'meal'
            base = 300
        if prop > 0.28:
            mult = 1.6
        elif prop > 0.14:
            mult = 1.15
        else:
            mult = 0.85
        est = int(round(base * mult))
        return label, est, 0.45

    # final fallback
    return 'unknown', 300, 0.4

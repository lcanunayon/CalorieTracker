# CalorieTracker (Prototype)

This is a small prototype Flask app that helps you log calories for breakfast, lunch, and dinner.

Features
- Upload a photo of your food — a MobileNet-based classifier guesses the food and maps to a rough calorie estimate.
- Manually override calorie values.
- Save entries to a local SQLite database and view a calendar with daily totals.

Requirements
- Windows PowerShell (instructions below)
- Python 3.10+ recommended

Quick start (PowerShell)
```powershell
cd d:\CalorieTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

Notes & Limitations
- The image-to-calorie mapping is heuristic: MobileNet class labels mapped to a small calorie table.
- TensorFlow installation can be heavy; if you prefer, replace `estimate_calories` in `utils.py` with a call to an external image-recognition API (e.g., hosted ML service) and return a calorie mapping.

Next steps you might want me to do:
- Add user accounts and export data as CSV
- Improve food-calorie mapping and portion-size estimation
- Integrate a cloud vision API for better recognition

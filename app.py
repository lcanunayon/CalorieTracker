import os
import datetime
import calendar as pycalendar
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from extensions import db
from werkzeug.utils import secure_filename
from utils import estimate_calories

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'dev-secret'

# initialize extensions
db.init_app(app)

with app.app_context():
    # import models after db is initialized to avoid circular imports
    from models import Entry
    db.create_all()


@app.route('/')
def index():
    today = datetime.date.today()
    entries = Entry.query.filter(Entry.date == today.isoformat()).all()
    totals = { 'breakfast': 0, 'lunch': 0, 'dinner': 0 }
    for e in entries:
        totals[e.meal] = totals.get(e.meal, 0) + (e.calories or 0)
    return render_template('index.html', date=today, totals=totals, entries=entries)


@app.route('/upload/<meal>', methods=['GET', 'POST'])
def upload(meal):
    meal = meal.lower()
    if meal not in ('breakfast', 'lunch', 'dinner'):
        flash('Meal must be breakfast, lunch or dinner')
        return redirect(url_for('index'))

    if request.method == 'POST':
        f = request.files.get('photo')
        manual_cal = request.form.get('manual_cal')
        notes = request.form.get('notes')
        date_str = request.form.get('date') or datetime.date.today().isoformat()

        filename = None
        predicted = None
        predicted_cal = None

        if f and f.filename:
            filename = secure_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(path)
            predicted, predicted_cal, confidence = estimate_calories(path)

        # prefer manual if provided
        calories = None
        if manual_cal:
            try:
                calories = int(manual_cal)
            except ValueError:
                calories = None

        if calories is None and predicted_cal is not None:
            calories = predicted_cal

        entry = Entry(date=date_str, meal=meal, food_estimate=predicted or '', calories=calories or 0, notes=notes or '', image_filename=filename)
        db.session.add(entry)
        db.session.commit()
        flash('Logged ' + meal)
        return redirect(url_for('index'))

    today = datetime.date.today().isoformat()
    return render_template('upload.html', meal=meal, date=today)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/calendar')
def calendar_view():
    # show current month
    now = datetime.date.today()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))
    cal = pycalendar.Calendar()
    month_days = list(cal.itermonthdates(year, month))

    # aggregate totals per day
    totals_by_day = {}
    for e in Entry.query.filter(Entry.date.like(f"{year}-%")).all():
        try:
            d = datetime.date.fromisoformat(e.date)
        except Exception:
            continue
        if d.month != month:
            continue
        totals_by_day.setdefault(d.isoformat(), 0)
        totals_by_day[d.isoformat()] += (e.calories or 0)

    weeks = []
    week = []
    for dt in month_days:
        week.append({ 'date': dt, 'total': totals_by_day.get(dt.isoformat(), 0) })
        if len(week) == 7:
            weeks.append(week)
            week = []

    return render_template('calendar.html', year=year, month=month, weeks=weeks)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

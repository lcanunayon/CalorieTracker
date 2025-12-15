import os
import datetime
import calendar as pycalendar
import uuid
from sqlalchemy.pool import NullPool
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from extensions import db
from werkzeug.utils import secure_filename
from utils import estimate_calories
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# file upload settings
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}


def _allowed_file(filename):
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def _unique_filename(original_filename: str) -> str:
    # generate a short unique name while preserving extension
    name = secure_filename(original_filename)
    base, ext = os.path.splitext(name)
    unique = uuid.uuid4().hex
    return f"{unique}{ext}"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# SQLite engine options: allow connections across threads and avoid pooled writes
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': { 'check_same_thread': False },
    'poolclass': NullPool,
}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')

# initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

with app.app_context():
    # import models after db is initialized to avoid circular imports
    from models import Entry, User
    try:
        db.create_all()
    except Exception as e:
        # avoid crashing at import time; show helpful message
        import traceback
        traceback.print_exc()
        print('WARNING: could not create DB schema automatically:', e)


@login_manager.user_loader
def load_user(user_id):
    from models import User
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


@app.route('/register', methods=['GET', 'POST'])
def register():
    from models import User
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password required')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registered and logged in')
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    from models import User
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in')
            return redirect(url_for('index'))
        flash('Invalid credentials')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    from models import Entry
    today = datetime.date.today()
    entries = Entry.query.filter(Entry.date == today.isoformat(), Entry.user_id == current_user.id).all()
    totals = { 'breakfast': 0, 'lunch': 0, 'dinner': 0 }
    for e in entries:
        totals[e.meal] = totals.get(e.meal, 0) + (e.calories or 0)
    return render_template('index.html', date=today, totals=totals, entries=entries)


@app.route('/upload/<meal>', methods=['GET', 'POST'])
@login_required
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
            if not _allowed_file(f.filename):
                flash('File type not allowed')
                return redirect(request.url)
            filename = _unique_filename(f.filename)
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

        entry = Entry(date=date_str, meal=meal, food_estimate=predicted or '', calories=calories or 0, notes=notes or '', image_filename=filename, user_id=current_user.id)
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
@login_required
def calendar_view():
    # show current month
    now = datetime.date.today()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))
    cal = pycalendar.Calendar()
    month_days = list(cal.itermonthdates(year, month))

    # aggregate totals per day
    totals_by_day = {}
    from models import Entry
    for e in Entry.query.filter(Entry.date.like(f"{year}-%"), Entry.user_id == current_user.id).all():
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


@app.route('/day/<date>')
@login_required
def day_view(date):
    # date expected as ISO yyyy-mm-dd
    try:
        dt = datetime.date.fromisoformat(date)
    except Exception:
        flash('Invalid date')
        return redirect(url_for('calendar_view'))
    from models import Entry
    entries = Entry.query.filter(Entry.date == date, Entry.user_id == current_user.id).all()
    totals = { 'breakfast': 0, 'lunch': 0, 'dinner': 0 }
    for e in entries:
        totals[e.meal] = totals.get(e.meal, 0) + (e.calories or 0)
    return render_template('day.html', date=dt, entries=entries, totals=totals)


@app.route('/entry/<int:entry_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    from models import Entry
    entry = Entry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        entry.date = request.form.get('date') or entry.date
        entry.meal = request.form.get('meal') or entry.meal
        manual_cal = request.form.get('manual_cal')
        if manual_cal:
            try:
                entry.calories = int(manual_cal)
            except ValueError:
                pass
        entry.notes = request.form.get('notes') or entry.notes
        # handle new photo upload
        f = request.files.get('photo')
        if f and f.filename:
            if not _allowed_file(f.filename):
                flash('File type not allowed')
                return redirect(request.url)
            filename = _unique_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(path)
            entry.image_filename = filename
            predicted, predicted_cal, conf = estimate_calories(path)
            if not manual_cal and predicted_cal:
                entry.calories = predicted_cal
            entry.food_estimate = predicted or entry.food_estimate

        db.session.commit()
        flash('Entry updated')
        return redirect(url_for('day_view', date=entry.date))

    return render_template('edit.html', entry=entry)


@app.route('/entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    from models import Entry
    entry = Entry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    date = entry.date
    # remove image file optionally
    if entry.image_filename:
        try:
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], entry.image_filename)
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass
    db.session.delete(entry)
    db.session.commit()
    flash('Entry deleted')
    return redirect(url_for('day_view', date=date))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, render_template, request, redirect
from flask import url_for, flash, session
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime
import re

from database import get_db, close_db, init_db

app = Flask(__name__)
app.secret_key = 'sports-day-secret-key-2027'

app.teardown_appcontext(close_db)


# -----------------------------
# DECORATORS
# -----------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------
# HOME PAGE
# -----------------------------

@app.route('/')
def index():
    db = get_db()

    sports = db.execute('''
    SELECT * FROM sports
    WHERE is_active = 1
    ''').fetchall()

    return render_template('index.html', sports=sports)


# -----------------------------
# REGISTER
# -----------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if not all([name, email, phone, password, confirm]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email format.', 'danger')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        db = get_db()

        existing = db.execute(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        ).fetchone()

        if existing:
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        db.execute('''
        INSERT INTO users(name, email, phone, password, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            name,
            email,
            phone,
            hashed_password,
            datetime.now().isoformat()
        ))

        db.commit()

        flash('Registration successful.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html')


# -----------------------------
# LOGIN
# -----------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()

        user = db.execute(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))

            return redirect(url_for('dashboard'))

        flash('Invalid credentials.', 'danger')

    return render_template('auth/login.html')


# -----------------------------
# LOGOUT
# -----------------------------

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# -----------------------------
# STUDENT DASHBOARD
# -----------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()

    user_id = session['user_id']

    registrations = db.execute('''
    SELECT registrations.*, sports.name AS sport_name
    FROM registrations
    JOIN sports ON registrations.sport_id = sports.id
    WHERE registrations.user_id = ?
    ''', (user_id,)).fetchall()

    total = len(registrations)
    pending = len([r for r in registrations if r['payment_status'] == 'pending'])
    approved = len([r for r in registrations if r['payment_status'] == 'approved'])

    return render_template(
        'student/dashboard.html',
        registrations=registrations,
        total=total,
        pending=pending,
        approved=approved
    )


# -----------------------------
# SPORTS LIST
# -----------------------------

@app.route('/sports')
@login_required
def sports():
    db = get_db()

    sports = db.execute('''
    SELECT * FROM sports
    WHERE is_active = 1
    ''').fetchall()

    registered_sports = db.execute('''
    SELECT sport_id FROM registrations
    WHERE user_id = ?
    ''', (session['user_id'],)).fetchall()

    registered_ids = [r['sport_id'] for r in registered_sports]

    return render_template(
        'student/sports_list.html',
        sports=sports,
        registered_ids=registered_ids
    )

# -----------------------------
# SPORT DETAILS
# -----------------------------

@app.route('/sports/<int:sport_id>', methods=['GET', 'POST'])
@login_required
def sport_detail(sport_id):
    db = get_db()

    sport = db.execute(
        'SELECT * FROM sports WHERE id = ?',
        (sport_id,)
    ).fetchone()

    if request.method == 'POST':
        existing = db.execute('''
        SELECT * FROM registrations
        WHERE user_id = ? AND sport_id = ?
        ''', (session['user_id'], sport_id)).fetchone()

        if existing:
            flash('Already registered.', 'warning')
            return redirect(url_for('sports'))

        cursor = db.execute('''
        INSERT INTO registrations(
            user_id, sport_id, registered_at
        )
        VALUES (?, ?, ?)
        ''', (
            session['user_id'],
            sport_id,
            datetime.now().isoformat()
        ))

        db.commit()

        registration_id = cursor.lastrowid

        flash('Registration successful.', 'success')

        return redirect(url_for('payment', registration_id=registration_id))

    return render_template('student/sport_detail.html', sport=sport)


# -----------------------------
# PAYMENT
# -----------------------------

@app.route('/pay/<int:registration_id>', methods=['GET', 'POST'])
@login_required
def payment(registration_id):
    db = get_db()

    registration = db.execute('''
    SELECT registrations.*, sports.name AS sport_name,
           sports.fee
    FROM registrations
    JOIN sports ON registrations.sport_id = sports.id
    WHERE registrations.id = ?
    ''', (registration_id,)).fetchone()

    if request.method == 'POST':
        transaction_id = request.form['transaction_id']

        db.execute('''
        UPDATE registrations
        SET payment_ref = ?
        WHERE id = ?
        ''', (transaction_id, registration_id))

        db.commit()

        flash(
            'Payment reference submitted. Awaiting admin approval.',
            'success'
        )

        return redirect(url_for('dashboard'))

    return render_template(
        'student/payment.html',
        registration=registration
    )


# -----------------------------
# MY REGISTRATIONS
# -----------------------------

@app.route('/my-registrations')
@login_required
def my_registrations():
    db = get_db()

    registrations = db.execute('''
    SELECT registrations.*, sports.name AS sport_name,
           sports.fee, sports.venue, sports.event_date
    FROM registrations
    JOIN sports ON registrations.sport_id = sports.id
    WHERE registrations.user_id = ?
    ''', (session['user_id'],)).fetchall()

    return render_template(
        'student/my_registrations.html',
        registrations=registrations
    )

# -----------------------------
# CANCEL REGISTRATION
# -----------------------------

@app.route('/cancel/<int:registration_id>', methods=['POST'])
@login_required
def cancel_registration(registration_id):
    db = get_db()

    registration = db.execute('''
    SELECT * FROM registrations
    WHERE id = ? AND user_id = ?
    ''', (registration_id, session['user_id'])).fetchone()

    if not registration:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_registrations'))

    if registration['payment_status'] != 'pending':
        flash('Only pending registrations can be cancelled.', 'danger')
        return redirect(url_for('my_registrations'))

    db.execute(
        'DELETE FROM registrations WHERE id = ?',
        (registration_id,)
    )

    db.commit()

    flash('Registration cancelled successfully.', 'success')

    return redirect(url_for('my_registrations'))


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()

    students = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='student'"
    ).fetchone()[0]

    sports = db.execute(
        'SELECT COUNT(*) FROM sports'
    ).fetchone()[0]

    registrations = db.execute(
        'SELECT COUNT(*) FROM registrations'
    ).fetchone()[0]

    pending = db.execute(
        "SELECT COUNT(*) FROM registrations WHERE payment_status='pending'"
    ).fetchone()[0]

    revenue = db.execute('''
    SELECT SUM(sports.fee)
    FROM registrations
    JOIN sports ON registrations.sport_id = sports.id
    WHERE registrations.payment_status = 'approved'
    ''').fetchone()[0]

    recent = db.execute('''
    SELECT users.name AS student_name,
           sports.name AS sport_name,
           registrations.payment_status
    FROM registrations
    JOIN users ON registrations.user_id = users.id
    JOIN sports ON registrations.sport_id = sports.id
    ORDER BY registrations.id DESC
    LIMIT 10
    ''').fetchall()

    return render_template(
        'admin/dashboard.html',
        students=students,
        sports=sports,
        registrations=registrations,
        pending=pending,
        revenue=revenue or 0,
        recent=recent
    )




# -----------------------------
# ADD SPORT
# -----------------------------

@app.route('/admin/sports')
@admin_required
def admin_sports():

    db = get_db()

    sports = db.execute(
        'SELECT * FROM sports'
    ).fetchall()

    return render_template(
        'admin/sports_list.html',
        sports=sports
    )


@app.route('/admin/sports/add', methods=['GET', 'POST'])
@admin_required
def add_sport():
    if request.method == 'POST':
        db = get_db()

        db.execute('''
        INSERT INTO sports(
            name, description, rules, fee,
            max_players, venue, event_date, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.form['name'],
            request.form['description'],
            request.form['rules'],
            request.form['fee'],
            request.form['max_players'],
            request.form['venue'],
            request.form['event_date'],
            datetime.now().isoformat()
        ))

        db.commit()

        flash('Sport added successfully.', 'success')
        return redirect(url_for('admin_sports'))

    return render_template('admin/sport_form.html', sport=None)


# -----------------------------
# EDIT SPORT
# -----------------------------

@app.route('/admin/sports/edit/<int:sport_id>', methods=['GET', 'POST'])
@admin_required
def edit_sport(sport_id):
    db = get_db()

    sport = db.execute(
        'SELECT * FROM sports WHERE id = ?',
        (sport_id,)
    ).fetchone()

    if request.method == 'POST':
        db.execute('''
        UPDATE sports
        SET name=?, description=?, rules=?, fee=?,
            max_players=?, venue=?, event_date=?
        WHERE id=?
        ''', (
            request.form['name'],
            request.form['description'],
            request.form['rules'],
            request.form['fee'],
            request.form['max_players'],
            request.form['venue'],
            request.form['event_date'],
            sport_id
        ))

        db.commit()

        flash('Sport updated successfully.', 'success')
        return redirect(url_for('admin_sports'))

    return render_template('admin/sport_form.html', sport=sport)


# -----------------------------
# DELETE SPORT
# -----------------------------

@app.route('/admin/sports/delete/<int:sport_id>', methods=['POST'])
@admin_required
def delete_sport(sport_id):
    db = get_db()

    existing = db.execute(
        'SELECT * FROM registrations WHERE sport_id = ?',
        (sport_id,)
    ).fetchone()

    if existing:
        flash('Cannot delete sport with active registrations.', 'danger')
        return redirect(url_for('admin_sports'))

    db.execute(
        'DELETE FROM sports WHERE id = ?',
        (sport_id,)
    )

    db.commit()

    flash('Sport deleted successfully.', 'success')

    return redirect(url_for('admin_sports'))


# -----------------------------
# ADMIN REGISTRATIONS
# -----------------------------

@app.route('/admin/registrations')
@admin_required
def admin_registrations():
    db = get_db()

    registrations = db.execute('''
    SELECT registrations.*, users.name AS student_name,
           users.email, sports.name AS sport_name,
           sports.fee
    FROM registrations
    JOIN users ON registrations.user_id = users.id
    JOIN sports ON registrations.sport_id = sports.id
    ORDER BY registrations.id DESC
    ''').fetchall()

    return render_template(
        'admin/registrations.html',
        registrations=registrations
    )


# -----------------------------
# UPDATE PAYMENT STATUS
# -----------------------------

@app.route('/admin/payment/<int:registration_id>', methods=['POST'])
@admin_required
def update_payment(registration_id):
    status = request.form['status']

    db = get_db()

    db.execute('''
    UPDATE registrations
    SET payment_status = ?
    WHERE id = ?
    ''', (status, registration_id))

    db.commit()

    flash('Payment status updated.', 'success')

    return redirect(url_for('admin_registrations'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
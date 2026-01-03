from flask import Flask, render_template, request, redirect, session, jsonify, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', b'\xe0\xac\xc1E\xc5\x96V2}\xf9\xbb\xed\xbd\xe4\xbe1\xf3\x197\x835&\x8e\xfe')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# PostgreSQL connection configuration
# Use DATABASE_URL from environment (Render) or fall back to local config
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Render provides DATABASE_URL - use it directly
    # Fix postgres:// to postgresql:// if needed
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    DB_CONFIG = DATABASE_URL
else:
    # Local development configuration
    DB_CONFIG = {
        'dbname': 'students_db',
        'user': 'postgres',
        'password': '0129',  # Replace with your local PostgreSQL password
        'host': 'localhost',
        'port': '5432'
    }


# Connect to database
def get_db():
    if isinstance(DB_CONFIG, str):
        # Use connection URL (for Render)
        con = psycopg2.connect(DB_CONFIG)
    else:
        # Use config dict (for local development)
        con = psycopg2.connect(**DB_CONFIG)
    return con


# Initialize database tables
def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """CREATE TABLE IF NOT EXISTS students
           (
               id
               SERIAL
               PRIMARY
               KEY,
               name
               TEXT
               NOT
               NULL,
               age
               INTEGER
               NOT
               NULL,
               course
               TEXT
               NOT
               NULL
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS attendance
        (
            id
            SERIAL
            PRIMARY
            KEY,
            student_id
            INTEGER
            NOT
            NULL,
            date
            TEXT
            NOT
            NULL,
            status
            TEXT
            CHECK (
            status
            IN
           (
            'present',
            'absent'
           )) NOT NULL,
            UNIQUE
           (
               student_id,
               date
           ),
            FOREIGN KEY
           (
               student_id
           ) REFERENCES students
           (
               id
           ) ON DELETE CASCADE
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users
           (
               id
               SERIAL
               PRIMARY
               KEY,
               username
               TEXT
               UNIQUE
               NOT
               NULL,
               password
               TEXT
               NOT
               NULL
           )"""
    )

    con.commit()
    cur.close()
    con.close()


init_db()


def is_logged_in():
    return "user_id" in session


# Decorator to protect routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to access this page.", "error")
            return redirect("/")
        return f(*args, **kwargs)

    return decorated_function


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('register.html')

        hashed_password = generate_password_hash(password)

        try:
            con = get_db()
            cur = con.cursor()
            cur.execute('''
                        INSERT INTO users (username, password)
                        VALUES (%s, %s)
                        ''', (username, hashed_password))
            con.commit()
            cur.close()
            con.close()

            flash("Account created successfully! Please log in.", "success")
            return redirect("/")

        except psycopg2.IntegrityError:
            flash("That username is already taken. Please choose another.", "error")
            return render_template('register.html')
        except psycopg2.Error as e:
            flash(f"Database error: {e}", "error")
            return render_template('register.html')

    return render_template('register.html')


@app.route("/")
def show_student():
    if not is_logged_in():
        return render_template("login.html")

    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM students ORDER BY name")
        students = cur.fetchall()
        cur.close()
        con.close()

        return render_template("index.html", students=students, username=session.get("username"))

    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("index.html", students=[], username=session.get("username"))


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        flash("Username and password required", "error")
        return redirect("/")

    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )
        user = cur.fetchone()
        cur.close()
        con.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid credentials", "error")
            return redirect("/")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect("/")

    except psycopg2.Error as e:
        flash(str(e), "error")
        return redirect("/")


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        try:
            first = request.form.get("first_name", "").strip()
            middle = request.form.get("middle_name", "").strip()
            last = request.form.get("last_name", "").strip()
            age = request.form.get("age", "").strip()
            course = request.form.get("course", "").strip()

            if not first or not last:
                flash("First name and last name are required", "error")
                return render_template("add.html")

            if not age.isdigit() or int(age) < 1 or int(age) > 150:
                flash("Please enter a valid age (1-150)", "error")
                return render_template("add.html")

            if not course:
                flash("Course is required", "error")
                return render_template("add.html")

            full_name = " ".join(part for part in [first, middle, last] if part)

            con = get_db()
            cur = con.cursor()
            cur.execute(
                "INSERT INTO students (name, age, course) VALUES (%s, %s, %s)",
                (full_name, int(age), course)
            )
            con.commit()
            cur.close()
            con.close()

            flash("Student added successfully!", "success")
            return redirect("/")

        except psycopg2.Error as e:
            flash(f"Database error: {e}", "error")
            return render_template("add.html")

    return render_template("add.html")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):
    if request.method == "POST":
        try:
            first = request.form.get("first_name", "").strip()
            middle = request.form.get("middle_name", "").strip()
            last = request.form.get("last_name", "").strip()
            age = request.form.get("age", "").strip()
            course = request.form.get("course", "").strip()

            if not first or not last:
                flash("First name and last name are required", "error")
                return redirect(f"/edit/{id}")

            if not age.isdigit() or int(age) < 1 or int(age) > 150:
                flash("Please enter a valid age (1-150)", "error")
                return redirect(f"/edit/{id}")

            if not course:
                flash("Course is required", "error")
                return redirect(f"/edit/{id}")

            full_name = " ".join(part for part in [first, middle, last] if part)

            con = get_db()
            cur = con.cursor()
            cur.execute(
                "UPDATE students SET name = %s, age = %s, course = %s WHERE id = %s",
                (full_name, int(age), course, id)
            )
            con.commit()
            cur.close()
            con.close()

            flash("Student updated successfully!", "success")
            return redirect("/")

        except psycopg2.Error as e:
            flash(f"Database error: {e}", "error")
            return redirect(f"/edit/{id}")

    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM students WHERE id = %s", (id,))
        student = cur.fetchone()
        cur.close()
        con.close()

        if not student:
            flash("Student not found", "error")
            return redirect("/")

        return render_template("edit.html", student=student)

    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return redirect("/")


@app.route("/delete/<int:id>")
@login_required
def delete_student(id):
    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name FROM students WHERE id = %s", (id,))
        student = cur.fetchone()

        if not student:
            flash("Student not found", "error")
            cur.close()
            con.close()
            return redirect("/")

        cur.execute("DELETE FROM attendance WHERE student_id = %s", (id,))
        cur.execute("DELETE FROM students WHERE id = %s", (id,))
        con.commit()
        cur.close()
        con.close()

        flash(f"Student deleted successfully!", "success")
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")

    return redirect("/")


@app.route("/attendance")
@login_required
def attendance_home():
    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
                    SELECT (SELECT COUNT(*) FROM students)                       AS total_students,
                           COUNT(DISTINCT a.date)                                AS total_days,
                           SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS total_present,
                           COUNT(a.id)                                           AS total_records
                    FROM attendance a
                    """)
        stats = cur.fetchone()
        cur.close()
        con.close()

        return render_template("attendance.html", stats=stats, today=date.today().isoformat())
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("attendance.html", stats=None, today=date.today().isoformat())


@app.route("/mark_attendance", methods=["GET", "POST"])
@login_required
def mark_attendance():
    if request.method == "POST":
        try:
            attendance_date = request.form.get("date", "").strip()

            if not attendance_date:
                flash("Date is required", "error")
                return redirect("/mark_attendance")

            con = get_db()
            cur = con.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT id FROM students")
            students = cur.fetchall()

            for student in students:
                student_id = student["id"]
                status = request.form.get(f"student_{student_id}", "absent")

                cur.execute("""
                            INSERT INTO attendance (student_id, date, status)
                            VALUES (%s, %s, %s) ON CONFLICT (student_id, date) 
                    DO
                            UPDATE SET status = EXCLUDED.status
                            """, (student_id, attendance_date, status))

            con.commit()
            cur.close()
            con.close()

            flash(f"Attendance marked for {attendance_date}", "success")
            return redirect("/attendance")

        except psycopg2.Error as e:
            flash(f"Database error: {e}", "error")
            return redirect("/mark_attendance")

    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM students ORDER BY name")
        students = cur.fetchall()
        cur.close()
        con.close()

        return render_template("mark_attendance.html", students=students, today=date.today().isoformat())
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("mark_attendance.html", students=[], today=date.today().isoformat())


@app.route("/view_attendance/<date_str>")
@login_required
def view_attendance(date_str):
    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
                    SELECT s.id,
                           s.name,
                           s.course,
                           COALESCE(a.status, 'not marked') as status
                    FROM students s
                             LEFT JOIN attendance a ON s.id = a.student_id AND a.date = %s
                    ORDER BY s.name
                    """, (date_str,))
        records = cur.fetchall()
        cur.close()
        con.close()

        return render_template("view_attendance.html", records=records, date=date_str)
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return redirect("/attendance")


@app.route("/report")
@login_required
def report():
    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
                    SELECT s.id,
                           s.name,
                           s.course,
                           COUNT(a.id)                                           AS total_days,
                           SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_days,
                           SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END)  AS absent_days,
                           CASE
                               WHEN COUNT(a.id) > 0
                                   THEN ROUND(
                                       CAST(SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS NUMERIC) * 100.0 /
                                       COUNT(a.id), 2)
                               ELSE 0
                               END                                               AS attendance_percentage
                    FROM students s
                             LEFT JOIN attendance a ON s.id = a.student_id
                    GROUP BY s.id
                    ORDER BY s.name
                    """)
        report_data = cur.fetchall()
        cur.close()
        con.close()

        return render_template("report.html", report=report_data)
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("report.html", report=[])


@app.route("/attendance_dates")
@login_required
def attendance_dates():
    try:
        con = get_db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
                    SELECT DISTINCT date, COUNT (*) as total, SUM (CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
                    FROM attendance
                    GROUP BY date
                    ORDER BY date DESC
                    """)
        dates = cur.fetchall()
        cur.close()
        con.close()

        return render_template("attendance_dates.html", dates=dates)
    except psycopg2.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("attendance_dates.html", dates=[])


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
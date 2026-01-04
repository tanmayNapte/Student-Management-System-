from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date
from dotenv import load_dotenv
import os

# -------------------- APP SETUP --------------------

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key-change-in-production")

# Handle both DATABASE_URL formats (Render uses postgresql://)
database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///students.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------- MODELS --------------------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    course = db.Column(db.String(100), nullable=False)

    attendance = db.relationship(
        "Attendance",
        backref="student",
        cascade="all, delete",
        lazy=True
    )


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="unique_student_date"),
    )

# -------------------- INIT --------------------

with app.app_context():
    db.create_all()

# -------------------- AUTH HELPERS --------------------

def is_logged_in():
    return "user_id" in session


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to access this page.", "error")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated

# -------------------- AUTH ROUTES --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        hashed = generate_password_hash(password)

        try:
            user = User(username=username, password=hashed)
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            flash("Username already exists.", "error")

    return render_template("register.html")


@app.route("/", methods=["GET", "POST"])
def login():
    # If already logged in, redirect to students page
    if is_logged_in():
        return redirect("/students")
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password required.", "error")
            return redirect("/")

        try:
            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password, password):
                flash("Invalid credentials.", "error")
                return redirect("/")

            session["user_id"] = user.id
            session["username"] = user.username
            return redirect("/students")
        except Exception as e:
            flash("Database error. Please try again.", "error")
            return redirect("/")

    return render_template("login.html")

# -------------------- STUDENTS --------------------

@app.route("/students")
@login_required
def show_students():
    try:
        students = Student.query.order_by(Student.name).all()
        return render_template("index.html", students=students)
    except Exception as e:
        flash("Error loading students.", "error")
        return render_template("index.html", students=[])


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        middle = request.form.get("middle_name", "").strip()
        last = request.form.get("last_name", "").strip()
        age = request.form.get("age", "").strip()
        course = request.form.get("course", "").strip()

        if not first or not last:
            flash("First name and last name are required.", "error")
            return render_template("add.html")

        if not age.isdigit() or int(age) < 1 or int(age) > 150:
            flash("Please enter a valid age (1-150).", "error")
            return render_template("add.html")

        if not course:
            flash("Course is required.", "error")
            return render_template("add.html")

        full_name = " ".join(x for x in [first, middle, last] if x)

        try:
            student = Student(name=full_name, age=int(age), course=course)
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully!", "success")
            return redirect("/students")
        except Exception as e:
            db.session.rollback()
            flash("Error adding student.", "error")

    return render_template("add.html")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):
    try:
        student = Student.query.get_or_404(id)
    except:
        flash("Student not found.", "error")
        return redirect("/students")

    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        middle = request.form.get("middle_name", "").strip()
        last = request.form.get("last_name", "").strip()
        age = request.form.get("age", "").strip()
        course = request.form.get("course", "").strip()

        if not first or not last:
            flash("First name and last name are required.", "error")
            return redirect(f"/edit/{id}")

        if not age.isdigit() or int(age) < 1 or int(age) > 150:
            flash("Please enter a valid age (1-150).", "error")
            return redirect(f"/edit/{id}")

        if not course:
            flash("Course is required.", "error")
            return redirect(f"/edit/{id}")

        try:
            student.name = " ".join(x for x in [first, middle, last] if x)
            student.age = int(age)
            student.course = course
            db.session.commit()
            flash("Student updated successfully!", "success")
            return redirect("/students")
        except Exception as e:
            db.session.rollback()
            flash("Error updating student.", "error")
            return redirect(f"/edit/{id}")

    return render_template("edit.html", student=student)


@app.route("/delete/<int:id>")
@login_required
def delete_student(id):
    try:
        student = Student.query.get_or_404(id)
        db.session.delete(student)
        db.session.commit()
        flash("Student deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error deleting student.", "error")
    
    return redirect("/students")

# -------------------- ATTENDANCE --------------------

@app.route("/attendance")
@login_required
def attendance_home():
    try:
        total_students = Student.query.count()
        records = Attendance.query.all()

        total_present = sum(1 for r in records if r.status == "present")
        total_days = len(set(r.date for r in records))

        stats = {
            "total_students": total_students,
            "total_days": total_days,
            "total_present": total_present,
            "total_records": len(records)
        }

        return render_template("attendance.html", stats=stats, today=date.today().isoformat())
    except Exception as e:
        flash("Error loading attendance data.", "error")
        return render_template("attendance.html", stats=None, today=date.today().isoformat())


@app.route("/mark_attendance", methods=["GET", "POST"])
@login_required
def mark_attendance():
    if request.method == "POST":
        att_date = request.form.get("date", "").strip()

        if not att_date:
            flash("Date is required.", "error")
            return redirect("/mark_attendance")

        try:
            students = Student.query.all()

            for s in students:
                status = request.form.get(f"student_{s.id}", "absent")

                record = Attendance.query.filter_by(
                    student_id=s.id,
                    date=att_date
                ).first()

                if record:
                    record.status = status
                else:
                    db.session.add(
                        Attendance(
                            student_id=s.id,
                            date=att_date,
                            status=status
                        )
                    )

            db.session.commit()
            flash(f"Attendance marked for {att_date}", "success")
            return redirect("/attendance")
        except Exception as e:
            db.session.rollback()
            flash("Error marking attendance.", "error")
            return redirect("/mark_attendance")

    try:
        students = Student.query.order_by(Student.name).all()
        return render_template("mark_attendance.html", students=students, today=date.today().isoformat())
    except Exception as e:
        flash("Error loading students.", "error")
        return render_template("mark_attendance.html", students=[], today=date.today().isoformat())


@app.route("/view_attendance/<date_str>")
@login_required
def view_attendance(date_str):
    try:
        students = Student.query.order_by(Student.name).all()
        data = []

        for s in students:
            rec = Attendance.query.filter_by(student_id=s.id, date=date_str).first()
            data.append({
                "id": s.id,
                "name": s.name,
                "course": s.course,
                "status": rec.status if rec else "not marked"
            })

        return render_template("view_attendance.html", records=data, date=date_str)
    except Exception as e:
        flash("Error loading attendance.", "error")
        return redirect("/attendance")


@app.route("/attendance_dates")
@login_required
def attendance_dates():
    try:
        # Get all unique dates with their statistics
        dates_dict = {}
        records = Attendance.query.all()
        
        for record in records:
            if record.date not in dates_dict:
                dates_dict[record.date] = {"total": 0, "present": 0}
            dates_dict[record.date]["total"] += 1
            if record.status == "present":
                dates_dict[record.date]["present"] += 1
        
        # Convert to list format expected by template
        dates = []
        for date_str, stats in sorted(dates_dict.items(), reverse=True):
            dates.append({
                "date": date_str,
                "total": stats["total"],
                "present": stats["present"]
            })
        
        return render_template("attendance_dates.html", dates=dates)
    except Exception as e:
        flash("Error loading attendance dates.", "error")
        return render_template("attendance_dates.html", dates=[])

# -------------------- REPORT --------------------

@app.route("/report")
@login_required
def report():
    try:
        students = Student.query.all()
        report_data = []

        for s in students:
            records = Attendance.query.filter_by(student_id=s.id).all()
            total = len(records)
            present = sum(1 for r in records if r.status == "present")
            absent = total - present
            percentage = round((present / total) * 100, 2) if total else 0

            report_data.append({
                "id": s.id,
                "name": s.name,
                "course": s.course,
                "total_days": total,
                "present_days": present,
                "absent_days": absent,
                "attendance_percentage": percentage
            })

        return render_template("report.html", report=report_data)
    except Exception as e:
        flash("Error generating report.", "error")
        return render_template("report.html", report=[])

# -------------------- LOGOUT --------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect("/")

# -------------------- RUN --------------------

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
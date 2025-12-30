from flask import Flask, render_template, request, redirect, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'  # Required for flash messages

# Connect to database with row factory
def get_db():
    con = sqlite3.connect("students1.db")
    con.row_factory = sqlite3.Row  # Access columns by name
    return con

# Initialize database tables
def init_db():
    with get_db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                course TEXT NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT CHECK(status IN ('present','absent')) NOT NULL,
                UNIQUE(student_id, date),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )"""
        )
        con.commit()

# Call init_db at startup
init_db()

@app.route("/")
def show_student():
    try:
        with get_db() as con:
            students = con.execute("SELECT * FROM students ORDER BY name").fetchall()
        return render_template("index.html", students=students)
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("index.html", students=[])

@app.route("/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        try:
            first = request.form.get("first_name", "").strip()
            middle = request.form.get("middle_name", "").strip()
            last = request.form.get("last_name", "").strip()
            age = request.form.get("age", "").strip()
            course = request.form.get("course", "").strip()
            
            # Validation
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
            
            with get_db() as con:
                con.execute(
                    "INSERT INTO students (name, age, course) VALUES (?, ?, ?)",
                    (full_name, int(age), course)
                )
                con.commit()
            
            flash("Student added successfully!", "success")
            return redirect("/")
            
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "error")
            return render_template("add.html")
    
    return render_template("add.html")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if request.method == "POST":
        try:
            first = request.form.get("first_name", "").strip()
            middle = request.form.get("middle_name", "").strip()
            last = request.form.get("last_name", "").strip()
            age = request.form.get("age", "").strip()
            course = request.form.get("course", "").strip()
            
            # Validation
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
            
            with get_db() as con:
                con.execute(
                    "UPDATE students SET name = ?, age = ?, course = ? WHERE id = ?",
                    (full_name, int(age), course, id)
                )
                con.commit()
            
            flash("Student updated successfully!", "success")
            return redirect("/")
            
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "error")
            return redirect(f"/edit/{id}")
    
    try:
        with get_db() as con:
            student = con.execute(
                "SELECT * FROM students WHERE id = ?", (id,)
            ).fetchone()
        
        if not student:
            flash("Student not found", "error")
            return redirect("/")
        
        return render_template("edit.html", student=student)
        
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return redirect("/")

@app.route("/delete/<int:id>")
def delete_student(id):
    try:
        with get_db() as con:
            # Check if student exists
            student = con.execute("SELECT name FROM students WHERE id = ?", (id,)).fetchone()
            if not student:
                flash("Student not found", "error")
                return redirect("/")
            
            # Delete attendance records first (or rely on CASCADE)
            con.execute("DELETE FROM attendance WHERE student_id = ?", (id,))
            con.execute("DELETE FROM students WHERE id = ?", (id,))
            con.commit()
        
        flash(f"Student deleted successfully!", "success")
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
    
    return redirect("/")

@app.route("/attendance")
def attendance_home():
    try:
        with get_db() as con:
            stats = con.execute("""
                SELECT
                    (SELECT COUNT(*) FROM students) AS total_students,
                    COUNT(DISTINCT a.date) AS total_days,
                    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS total_present,
                    COUNT(a.id) AS total_records
                FROM attendance a
            """).fetchone()
        
        return render_template("attendance.html", stats=stats, today=date.today().isoformat())
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("attendance.html", stats=None, today=date.today().isoformat())

@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if request.method == "POST":
        try:
            attendance_date = request.form.get("date", "").strip()
            
            if not attendance_date:
                flash("Date is required", "error")
                return redirect("/mark_attendance")
            
            with get_db() as con:
                students = con.execute("SELECT id FROM students").fetchall()
                
                for student in students:
                    student_id = student["id"]
                    status = request.form.get(f"student_{student_id}", "absent")
                    
                    con.execute("""
                        INSERT OR REPLACE INTO attendance 
                        (student_id, date, status) VALUES (?, ?, ?)
                    """, (student_id, attendance_date, status))
                
                con.commit()
            
            flash(f"Attendance marked for {attendance_date}", "success")
            return redirect("/attendance")
            
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "error")
            return redirect("/mark_attendance")
    
    try:
        with get_db() as con:
            students = con.execute("SELECT * FROM students ORDER BY name").fetchall()
        
        return render_template("mark_attendance.html", students=students, today=date.today().isoformat())
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("mark_attendance.html", students=[], today=date.today().isoformat())

@app.route("/view_attendance/<date_str>")
def view_attendance(date_str):
    try:
        with get_db() as con:
            records = con.execute("""
                SELECT s.id, s.name, s.course, 
                       COALESCE(a.status, 'not marked') as status
                FROM students s
                LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
                ORDER BY s.name
            """, (date_str,)).fetchall()
        
        return render_template("view_attendance.html", records=records, date=date_str)
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return redirect("/attendance")

@app.route("/report")
def report():
    try:
        with get_db() as con:
            report_data = con.execute("""
                SELECT s.id, s.name, s.course,
                       COUNT(a.id) AS total_days,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_days,
                       SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_days,
                       CASE 
                           WHEN COUNT(a.id) > 0 
                           THEN ROUND(SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) * 100.0 / COUNT(a.id), 2)
                           ELSE 0 
                       END AS attendance_percentage
                FROM students s
                LEFT JOIN attendance a ON s.id = a.student_id
                GROUP BY s.id
                ORDER BY s.name
            """).fetchall()
        
        return render_template("report.html", report=report_data)
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("report.html", report=[])

@app.route("/attendance_dates")
def attendance_dates():
    try:
        with get_db() as con:
            dates = con.execute("""
                SELECT DISTINCT date, 
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
                FROM attendance
                GROUP BY date
                ORDER BY date DESC
            """).fetchall()
        
        return render_template("attendance_dates.html", dates=dates)
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "error")
        return render_template("attendance_dates.html", dates=[])

if __name__ == "__main__":
    app.run(debug=True)
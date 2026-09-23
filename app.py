"""
Campus Event Dashboard
-----------------------
A Flask + SQLite web app for managing campus events, student registrations,
and attendance, with a live stats dashboard.

Only dependency: Flask (uses Python's built-in sqlite3 module for storage).

Run:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000
"""

import os
import sqlite3
from datetime import datetime, date
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DB_PATH = Path(__file__).parent / "campus_events.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'General',
    venue TEXT DEFAULT '',
    event_date TEXT NOT NULL,
    event_time TEXT DEFAULT '',
    capacity INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT DEFAULT '',
    year TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    registered_at TEXT NOT NULL,
    attended INTEGER DEFAULT 0,
    UNIQUE(event_id, student_id)
);
"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


@app.template_filter("prettydate")
def prettydate(iso_str):
    """Format an ISO date string (YYYY-MM-DD) as '23 Sep 2026'."""
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return iso_str


# ---------------------------------------------------------------------------
# Dashboard (home)
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    db = get_db()
    events = db.execute("SELECT * FROM event ORDER BY event_date").fetchall()

    total_events = len(events)
    total_students = db.execute("SELECT COUNT(*) c FROM student").fetchone()["c"]
    total_registrations = db.execute(
        "SELECT COUNT(*) c FROM registration"
    ).fetchone()["c"]
    total_attended = db.execute(
        "SELECT COUNT(*) c FROM registration WHERE attended = 1"
    ).fetchone()["c"]

    attendance_rate = (
        round(100 * total_attended / total_registrations, 1)
        if total_registrations
        else 0
    )

    today = date.today().isoformat()
    upcoming = db.execute(
        "SELECT * FROM event WHERE event_date >= ? ORDER BY event_date LIMIT 5",
        (today,),
    ).fetchall()

    chart_labels, chart_registered, chart_attended, category_counts = [], [], [], {}
    for e in events:
        reg_count = db.execute(
            "SELECT COUNT(*) c FROM registration WHERE event_id = ?", (e["id"],)
        ).fetchone()["c"]
        att_count = db.execute(
            "SELECT COUNT(*) c FROM registration WHERE event_id = ? AND attended = 1",
            (e["id"],),
        ).fetchone()["c"]
        chart_labels.append(e["name"])
        chart_registered.append(reg_count)
        chart_attended.append(att_count)
        category_counts[e["category"]] = category_counts.get(e["category"], 0) + 1

    upcoming_with_counts = []
    for e in upcoming:
        reg_count = db.execute(
            "SELECT COUNT(*) c FROM registration WHERE event_id = ?", (e["id"],)
        ).fetchone()["c"]
        upcoming_with_counts.append({**dict(e), "registered_count": reg_count})

    return render_template(
        "index.html",
        total_events=total_events,
        total_students=total_students,
        total_registrations=total_registrations,
        attendance_rate=attendance_rate,
        upcoming=upcoming_with_counts,
        chart_labels=chart_labels,
        chart_registered=chart_registered,
        chart_attended=chart_attended,
        category_labels=list(category_counts.keys()),
        category_values=list(category_counts.values()),
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.route("/events")
def events_list():
    db = get_db()
    events = db.execute("SELECT * FROM event ORDER BY event_date").fetchall()
    today = date.today().isoformat()
    enriched = []
    for e in events:
        reg_count = db.execute(
            "SELECT COUNT(*) c FROM registration WHERE event_id = ?", (e["id"],)
        ).fetchone()["c"]
        enriched.append(
            {
                **dict(e),
                "registered_count": reg_count,
                "is_upcoming": e["event_date"] >= today,
            }
        )
    return render_template("events.html", events=enriched)


@app.route("/events/new", methods=["GET", "POST"])
def event_new():
    if request.method == "POST":
        try:
            event_date = parse_date(request.form["event_date"])
        except ValueError:
            flash("Please enter a valid date.", "danger")
            return redirect(url_for("event_new"))

        name = request.form["name"].strip()
        db = get_db()
        db.execute(
            """INSERT INTO event (name, description, category, venue, event_date, event_time, capacity)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                request.form.get("description", "").strip(),
                request.form.get("category", "General").strip() or "General",
                request.form.get("venue", "").strip(),
                event_date.isoformat(),
                request.form.get("event_time", "").strip(),
                int(request.form.get("capacity") or 0),
            ),
        )
        db.commit()
        flash(f'Event "{name}" created.', "success")
        return redirect(url_for("events_list"))

    return render_template("event_form.html", event=None)


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def event_edit(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        flash("Event not found.", "danger")
        return redirect(url_for("events_list"))

    if request.method == "POST":
        try:
            event_date = parse_date(request.form["event_date"])
        except ValueError:
            flash("Please enter a valid date.", "danger")
            return redirect(url_for("event_edit", event_id=event_id))

        name = request.form["name"].strip()
        db.execute(
            """UPDATE event SET name=?, description=?, category=?, venue=?,
               event_date=?, event_time=?, capacity=? WHERE id=?""",
            (
                name,
                request.form.get("description", "").strip(),
                request.form.get("category", "General").strip() or "General",
                request.form.get("venue", "").strip(),
                event_date.isoformat(),
                request.form.get("event_time", "").strip(),
                int(request.form.get("capacity") or 0),
                event_id,
            ),
        )
        db.commit()
        flash(f'Event "{name}" updated.', "success")
        return redirect(url_for("events_list"))

    return render_template("event_form.html", event=event)


@app.route("/events/<int:event_id>/delete", methods=["POST"])
def event_delete(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
    db.execute("DELETE FROM event WHERE id = ?", (event_id,))
    db.commit()
    if event:
        flash(f'Event "{event["name"]}" deleted.', "info")
    return redirect(url_for("events_list"))


@app.route("/events/<int:event_id>")
def event_detail(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        flash("Event not found.", "danger")
        return redirect(url_for("events_list"))

    registrations = db.execute(
        """SELECT r.id as reg_id, r.attended, s.id as student_id, s.name, s.email, s.department
           FROM registration r JOIN student s ON r.student_id = s.id
           WHERE r.event_id = ? ORDER BY s.name""",
        (event_id,),
    ).fetchall()

    already_ids = {r["student_id"] for r in registrations}
    available_students = db.execute(
        "SELECT * FROM student ORDER BY name"
    ).fetchall()

    today = date.today().isoformat()
    event_dict = dict(event)
    event_dict["is_upcoming"] = event["event_date"] >= today
    event_dict["registered_count"] = len(registrations)
    event_dict["attended_count"] = sum(1 for r in registrations if r["attended"])

    return render_template(
        "event_detail.html",
        event=event_dict,
        registrations=registrations,
        available_students=available_students,
        already_ids=already_ids,
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@app.route("/students")
def students_list():
    db = get_db()
    students = db.execute("SELECT * FROM student ORDER BY name").fetchall()
    return render_template("students.html", students=students)


@app.route("/students/new", methods=["POST"])
def student_new():
    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    department = request.form.get("department", "").strip()
    year = request.form.get("year", "").strip()

    db = get_db()
    existing = db.execute(
        "SELECT id FROM student WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        flash("A student with that email already exists.", "danger")
        return redirect(url_for("students_list"))

    db.execute(
        "INSERT INTO student (name, email, department, year) VALUES (?, ?, ?, ?)",
        (name, email, department, year),
    )
    db.commit()
    flash(f'Student "{name}" added.', "success")
    return redirect(url_for("students_list"))


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def student_delete(student_id):
    db = get_db()
    db.execute("DELETE FROM student WHERE id = ?", (student_id,))
    db.commit()
    flash("Student removed.", "info")
    return redirect(url_for("students_list"))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@app.route("/events/<int:event_id>/register", methods=["POST"])
def register_student(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
    student_id = request.form.get("student_id")

    if not student_id:
        flash("Select a student to register.", "danger")
        return redirect(url_for("event_detail", event_id=event_id))

    if event["capacity"]:
        reg_count = db.execute(
            "SELECT COUNT(*) c FROM registration WHERE event_id = ?", (event_id,)
        ).fetchone()["c"]
        if reg_count >= event["capacity"]:
            flash("This event is at full capacity.", "danger")
            return redirect(url_for("event_detail", event_id=event_id))

    existing = db.execute(
        "SELECT id FROM registration WHERE event_id = ? AND student_id = ?",
        (event_id, student_id),
    ).fetchone()
    if existing:
        flash("Student is already registered for this event.", "warning")
        return redirect(url_for("event_detail", event_id=event_id))

    db.execute(
        "INSERT INTO registration (event_id, student_id, registered_at, attended) VALUES (?, ?, ?, 0)",
        (event_id, student_id, datetime.now().isoformat()),
    )
    db.commit()
    flash("Student registered.", "success")
    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/registrations/<int:reg_id>/unregister", methods=["POST"])
def unregister_student(reg_id):
    db = get_db()
    reg = db.execute(
        "SELECT event_id FROM registration WHERE id = ?", (reg_id,)
    ).fetchone()
    db.execute("DELETE FROM registration WHERE id = ?", (reg_id,))
    db.commit()
    flash("Registration removed.", "info")
    return redirect(url_for("event_detail", event_id=reg["event_id"] if reg else 1))


@app.route("/registrations/<int:reg_id>/toggle-attendance", methods=["POST"])
def toggle_attendance(reg_id):
    db = get_db()
    reg = db.execute(
        "SELECT * FROM registration WHERE id = ?", (reg_id,)
    ).fetchone()
    if reg:
        db.execute(
            "UPDATE registration SET attended = ? WHERE id = ?",
            (0 if reg["attended"] else 1, reg_id),
        )
        db.commit()
    return redirect(url_for("event_detail", event_id=reg["event_id"] if reg else 1))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)

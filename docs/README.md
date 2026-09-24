# Campus Event Dashboard

A simple, self-contained Flask web app for running campus events: create events,
register students, take attendance, and see everything on a live stats dashboard.

## Features
- **Dashboard** — total events, students, registrations, attendance rate, plus
  charts (registrations vs. attendance per event, events by category)
- **Events** — create, edit, delete events (name, category, venue, date/time, capacity)
- **Students** — add/remove a student directory (name, email, department, year)
- **Registration** — register students to events (respects capacity limits, prevents duplicates)
- **Attendance** — one-click toggle to mark a registered student as attended

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The only dependency is Flask — data is stored in a local SQLite file
(`campus_events.db`, created automatically on first run) using Python's
built-in `sqlite3` module, so there's nothing else to install or configure.

## Project structure

```
campus-events-dashboard/
├── app.py                  # Flask app: routes + database logic
├── requirements.txt
├── campus_events.db        # created automatically on first run
├── static/
│   └── style.css
└── templates/
    ├── base.html            # shared layout + nav
    ├── index.html            # dashboard (stats + charts)
    ├── events.html            # events list
    ├── event_form.html         # create/edit event
    ├── event_detail.html        # single event: register students, mark attendance
    └── students.html           # student directory
```

## Notes / ideas to extend
- Add login/roles (e.g. only event organizers can create events) with Flask-Login
- Export the registered-student list per event as CSV
- Email confirmation on registration (Flask-Mail)
- QR-code check-in for attendance instead of manual toggling
- Deploy with `gunicorn` behind Nginx, or on Render/Railway/PythonAnywhere for
  campus-wide access (swap the dev server for a production WSGI server first)

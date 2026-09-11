# webapp

The Django app behind fitness-tracker. It serves the personal homepage and a
small "Training" section with an interactive strength/conditioning tracker
(plus placeholder pages for Spanish and reading consistency).

This is separate from the `site/` folder at the repo root, which is a static
HTML/CSS/JS portfolio page.

## Stack

- Python 3.14, Django 5.2
- SQLite (`db.sqlite3`, checked in for local/dev use)
- Django templates + vanilla CSS/JS (`static/`), no frontend build step
- Single-user auth via Django's built-in auth (`django.contrib.auth`) --
  there's no signup flow, just a login page backed by a superuser account

## Project layout

```
webapp/
  config/           Project settings, root URLconf, WSGI/ASGI entrypoints
  pages/            Public home page ("/")
  training/         Training hub + physical/spanish/reading trackers,
                     JSON API for the workout tracker, week/day editor
  templates/         Shared templates (base.html, login)
  static/            Shared CSS/JS
  manage.py
  requirements.txt
  db.sqlite3
```

### `pages` app

Just the home page (`/`) -- bio, projects, contact links.

### `training` app

- `/training/` -- hub linking to the three trackers below
- `/training/physical/` -- 12-week strength/conditioning log built from a
  Week/Day editor: `Phase` (a week-range like "Ramp-In", 2 weeks),
  `Workout` (e.g. Push/Pull/Legs, with a name/description/color),
  `PhaseDay` (which workout, if any, falls on each weekday of a phase), and
  `Exercise` (rows in a workout's checklist -- sets/reps or a plain
  checkbox for cardio/stretch). Checking off a set writes a `CompletedSet`
  scoped to the user and the calendar day, so progress persists across
  refreshes and resets each new day.
- `/training/spanish/` and `/training/reading/` -- placeholder tracking
  pages
- `/training/edit/` -- add/edit/delete workouts and phases
- `/training/api/...` -- JSON endpoints the physical tracker's JS calls to
  read the schedule and toggle sets

All training views require login (`@login_required`); `LOGIN_URL` sends
you to `/accounts/login/`.

## Local setup

```bash
cd webapp
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Verify Django actually landed in the venv before moving on -- on this Mac,
`pip install -r requirements.txt` has previously appeared to succeed
without actually installing Django into a fresh venv:

```bash
python3 -m pip show django          # should print a version
which python                        # should point inside webapp/.venv/bin/
```

If Django's missing, re-run with the module form (not bare `pip`), and if
that still doesn't work, make sure the venv's own pip is intact:

```bash
.venv/bin/python3 -m ensurepip --upgrade
python3 -m pip install -r requirements.txt
```

Then set up the database and a login:

```bash
python3 manage.py migrate
python3 manage.py createsuperuser
```

Optionally seed sample workouts/phases for the physical tracker:

```bash
python3 manage.py seed_training
```

Run the dev server:

```bash
python3 manage.py runserver
```

Visit `http://127.0.0.1:8000/`. Log in at `/accounts/login/` (or
`/admin/`) with the superuser you created to reach `/training/`.

## Notes

- `DEBUG = True` and a checked-in `SECRET_KEY` in `config/settings.py` --
  fine for local use, not meant for production as-is.
- `ALLOWED_HOSTS` is limited to `localhost`/`127.0.0.1`.
- `TIME_ZONE` is set to `America/Chicago`.

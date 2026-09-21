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

## Native API (`/api/v1/`)

The native-client API is separate from the browser UI and uses JSON plus an
`Authorization: Bearer <access-token>` header. The existing `/training/api/`
endpoints still use the Django login session and CSRF protections unchanged.

Install dependencies and apply the SimpleJWT blacklist migrations:

```bash
python3 -m pip install -r requirements.txt
python3 manage.py migrate
```

Get a token pair with a username and password:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"your-user","password":"your-password"}'
```

Access tokens expire after 15 minutes. Refresh tokens expire after 30 days;
every refresh rotates the token and blacklists the submitted one, so replace
the saved refresh token with the returned value immediately. Logout submits
the stored refresh token and blacklists it:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/logout/ \
  -H 'Authorization: Bearer <access-token>' \
  -H 'Content-Type: application/json' -d '{"refresh":"<refresh-token>"}'
```

Client data endpoints require a client profile with an active assignment:

- `GET /api/v1/me/` — identity, all role names, and profile IDs.
- `GET /api/v1/plans/active/` — active plan and assignment metadata.
- `GET /api/v1/plans/active/schedule/` — ordered phases, weeks, weekdays,
  workouts, nutrients, supplements, and weekly tallies.
- `GET /api/v1/workouts/<id>/` — exercises plus today’s completion state.
- `PUT`/`DELETE /api/v1/exercises/<id>/sets/<set_number>/completion/` — set
  or clear one of today’s completed sets.
- `PUT`/`DELETE /api/v1/weeks/<week_id>/workouts/<workout_id>/completion/` —
  set or clear today’s workout completion and receive the updated week tally.

The two `PUT` endpoints are idempotent; repeated calls leave completion set,
and repeated `DELETE` calls leave it clear. Store JWTs only in the native
platform’s secure credential store.

The public OpenAPI contract and self-hosted documentation are available at
`/api/v1/schema/`, `/api/v1/docs/`, and `/api/v1/redoc/`. The documentation is
public; all fitness data endpoints remain authenticated.

## Notes

- `DEBUG = True` and a checked-in `SECRET_KEY` in `config/settings.py` --
  fine for local use, not meant for production as-is.
- `ALLOWED_HOSTS` is limited to `localhost`/`127.0.0.1`.
- `TIME_ZONE` is set to `America/Chicago`.

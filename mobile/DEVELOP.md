# Developing the iOS app in the Simulator

The Django API runs in one terminal and the Expo app in another. Expo Go opens
the app in a simulated iPhone on your Mac, so you don't need a physical phone.

| | |
|---|---|
| Repo root | the folder with `manage.py` (your clone or worktree) |
| API URL the app uses | `http://127.0.0.1:8000` (override with `EXPO_PUBLIC_API_BASE_URL`) |
| Demo logins | see [Sign in to the app](#sign-in-to-the-app) |

## One-time Mac setup

Do this once per Mac. Skip ahead to [Every time](#every-time-two-terminals)
if `xcrun simctl list devices available | grep iPhone` already lists iPhones.

1. **Install Xcode** from the Mac App Store (free; roughly 15–40 GB with the
   iOS simulator runtime).

2. **Open Xcode once and accept the license**, and let it install its extra
   components. Or from the terminal:

   ```bash
   sudo xcodebuild -license accept
   ```

3. **Point the command-line tools at Xcode:**

   ```bash
   sudo xcode-select -s /Applications/Xcode.app
   ```

   No trailing period: `/Applications/Xcode.app.` fails with
   "invalid developer directory".

4. **Install the iOS simulator runtime.** In Xcode, open
   **Settings → Components** and download the latest iOS platform. Then check:

   ```bash
   xcode-select -p   # /Applications/Xcode.app/Contents/Developer
   xcrun simctl list devices available | grep iPhone
   ```

5. **Create the Python venv and local database** (once per clone or worktree,
   from the repo root; `.venv/` and `db.sqlite3` are gitignored):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python3 -m pip install -r requirements.txt
   python3 -m pip show django   # confirm Django really installed
   python3 manage.py migrate
   python3 manage.py seed_demo_accounts
   ```

   `seed_demo_accounts` creates one login per role, linked together, with a
   sample plan. See [Sign in to the app](#sign-in-to-the-app).

6. **Install the app's JavaScript packages:**

   ```bash
   cd mobile
   npm install
   ```

## Every time: two terminals

Start the API first, then the app. Both run until you press Ctrl+C.

**Terminal 1: API** (repo root)

```bash
source .venv/bin/activate
python3 manage.py runserver
```

**Terminal 2: app** (repo root)

```bash
cd mobile
npx expo start
```

Press `i` to open the iOS Simulator. The first launch installs Expo Go in it.
Press `r` in terminal 2 to reload the app, and `Cmd+D` in the simulator for
the developer menu.

## Sign in to the app

The tabs you see depend on the account's roles, so each demo account shows a
different part of the app. They're linked: Owner1 owns the gym, Trainer1 works
there, and Client1 is Trainer1's client with a two-phase sample plan.

| Username | Password | Role | Tabs |
|---|---|---|---|
| `Client1` | `Client1pass` | Client | Today, Nutrition, Profile |
| `Trainer1` | `Trainer1pass` | Trainer | Clients, Plans, Profile |
| `Owner1` | `Owner1pass` | Gym owner | Clients, Plans, Trainers, Profile |

- **Switch accounts** with **Profile → Sign out**, then sign in as someone
  else. Each account starts with empty local data on the device, so you never
  see another account's cached screens.
- **The login is remembered** in the simulator's keychain between runs. Sign
  out to get back to the sign-in screen.
- **One account with every role:** create your own superuser and seed it.
  It sees all six tabs; iOS puts the fifth and sixth under "More".

  ```bash
  python3 manage.py createsuperuser
  python3 manage.py seed_training --username <your-username>
  ```

- **See a trainer's change reach a client:** sign in as Trainer1, open
  Clients → Client1 → Edit plan, change a workout, sign out, then sign in as
  Client1 and check Today.

### Are these passwords safe to share?

Yes, for local development. They're the fixed demo credentials already in
`training/management/commands/seed_demo_accounts.py`, and the accounts exist
only in databases where someone ran that command, normally your own
`db.sqlite3`.

**Never run `seed_demo_accounts` against a shared or production database.**
Anyone who has read this file could sign in to those accounts there.

## Try the offline flow

Check-offs are saved on the device first and synced to `POST /api/v1/sync/`
when the app opens, returns to the foreground, reconnects, or right after a
change.

1. Sign in as Client1 and open a workout from Today while connected.
2. Stop terminal 1 (or turn the Mac's Wi-Fi off) and check off some sets.
   They stay checked, and Today says changes are waiting to sync.
3. Start the API again (or reconnect). The changes sync, and the web app at
   `http://127.0.0.1:8000/training/physical/` shows them on today's date.

Screens you've opened before still show their last saved copy while offline.
Trainer and owner edits need a connection.

## When something goes wrong

**"Couldn't reach the server" or "You're offline" with the API running**
Make sure terminal 1 is running. If `mobile/.env.local` exists from phone
testing, it points the app at your LAN IP. Delete it and restart with a
cleared cache:

```bash
rm .env.local
npx expo start -c
```

**"Incorrect username or password"**
Each clone or worktree has its own `db.sqlite3`. Seed the accounts in the one
you're running from (`python3 manage.py seed_demo_accounts`), or reset a
password with `python3 manage.py changepassword <username>`.

**Expo Go: "There was a problem running the requested project. Could not connect to the server."**
Terminal 2 (Metro) isn't running. Start `npx expo start` and press `i`.

**Pressing `i` says no simulator or Xcode found**
Repeat steps 3 and 4 of the setup. `xcode-select -p` must print the Xcode
path, not `/Library/Developer/CommandLineTools`.

**`No module named django`**
The venv isn't active in this terminal. Run `source .venv/bin/activate` from
the repo root.

**Expo Go asks to update, or the app shows a stale screen**
Accept the update, then restart with `npx expo start -c`. To start over
completely, quit the simulator and run `xcrun simctl erase all`.

**Today is empty or says "No plan yet"**
The account has no active plan. Run `python3 manage.py seed_demo_accounts`,
or for your own account `python3 manage.py seed_training --username <your-username>`.

## Useful commands

From `mobile/`:

```bash
npm run typecheck    # TypeScript
npx expo lint        # ESLint
npx expo-doctor      # dependency and config checks
npm run api:schema   # re-export the OpenAPI schema (Django venv active)
npm run api:types    # regenerate src/api/schema.d.ts from it
```

Hosting is tracked in FIT-7 and TestFlight in FIT-6.

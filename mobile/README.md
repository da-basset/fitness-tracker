# Fitness Tracker iOS app

Expo app (Expo Router, TypeScript) for the Django native API at `/api/v1/`.
Clients log workouts, including offline; trainers and gym owners manage
clients and plans.

**Developing on a Mac? Start with [DEVELOP.md](DEVELOP.md)**: iOS Simulator
setup, the two-terminal routine, demo logins for each role, and fixes for
common errors.

## Run it locally on your iPhone (Expo Go)

You need the Expo Go app on the phone, and the phone and Mac on the same Wi-Fi.

1. **Start the API on all interfaces** (from the repo root, inside your venv).
   The phone can't reach `127.0.0.1`, so allow your Mac's LAN IP:

   ```bash
   IP=$(ipconfig getifaddr en0)
   DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,$IP" python3 manage.py runserver 0.0.0.0:8000
   ```

2. **Point the app at it** (in `mobile/`):

   ```bash
   echo "EXPO_PUBLIC_API_BASE_URL=http://$(ipconfig getifaddr en0):8000" > .env.local
   npm install
   npx expo start
   ```

3. Scan the QR code with the iPhone camera to open it in Expo Go. Sign in with
   any Django user (e.g. one from `createsuperuser`).

Restart `npx expo start` after changing `.env.local`. Env vars are inlined
at bundle time.

If your Wi-Fi blocks device-to-device traffic, use `npx expo start --tunnel`
for the app and expose the API with a tunnel of your own.

## API types

The client is typed from the Django OpenAPI schema. After changing the API:

```bash
npm run api:schema   # needs the Django venv active
npm run api:types
```

## Checks

```bash
npm run typecheck
npx expo lint
```

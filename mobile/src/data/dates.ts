/** The device's IANA time zone, e.g. "America/Chicago". */
export function deviceTimeZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Today's calendar date (YYYY-MM-DD) where the user is, not in UTC. */
export function localToday(now = new Date()) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** Monday..Sunday bounds (YYYY-MM-DD) of the calendar week holding `date`. */
export function weekBounds(date: string) {
  const [y, m, d] = date.split('-').map(Number);
  const day = new Date(y, m - 1, d);
  const offset = (day.getDay() + 6) % 7; // Monday = 0
  const monday = new Date(y, m - 1, d - offset);
  const sunday = new Date(y, m - 1, d - offset + 6);
  return { start: localToday(monday), end: localToday(sunday) };
}

export function formatLongDate(date: string) {
  const [y, m, d] = date.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

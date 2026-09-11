// Wait for the HTML to finish loading before touching the DOM. Our <script>
// tag is at the end of <body>, so in practice everything above it already
// exists by the time this file runs -- but wrapping code in DOMContentLoaded
// is a good habit regardless: if this script ever moves to <head>, or gets
// loaded a different way, the code still won't run early and silently fail
// (document.getElementById returns null for anything that doesn't exist yet).
document.addEventListener("DOMContentLoaded", () => {
  // --- Auto-updating footer year ---
  const yearEl = document.getElementById("year");
  if (yearEl) {
    // textContent sets plain text (not textContent = innerHTML, which
    // parses whatever string you give it as HTML -- textContent is the
    // safer default whenever you're just inserting text, not markup).
    yearEl.textContent = new Date().getFullYear();
  }

  // --- Smooth scroll for the nav links ---
  // By default, clicking <a href="#about"> makes the browser jump
  // instantly. We intercept the click, cancel that default jump, and
  // scroll there smoothly instead.
  document.querySelectorAll('nav a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = link.getAttribute("href").slice(1); // "#about" -> "about"
      const target = document.getElementById(targetId);
      if (!target) return;

      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth" });
    });
  });

  initTheme();
  initSettingsPanel();
});

const THEME_KEY = "theme"; // the localStorage key we save the choice under

// Adds or removes data-theme="dark" on <html>. The CSS variable overrides
// in style.css (:root[data-theme="dark"] { ... }) key off this exact
// attribute -- this function is the only place that touches it.
function applyTheme(theme) {
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

// localStorage persists small key/value pairs in the browser across page
// loads and browser restarts -- unlike a normal JS variable, which resets
// every time the page reloads. It's wrapped in try/catch because some
// browser settings (e.g. certain private-browsing modes) block it entirely,
// and an unhandled error here would stop the rest of the script from
// running.
function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch (err) {
    return null;
  }
}

// Reads the values main.js needs off <body>'s data-* attributes (set by
// base.html). These come from the server, so they carry the logged-in
// user's saved preference -- something localStorage alone can't do,
// since localStorage is per-browser, not per-account.
function isAuthenticated() {
  return document.body.dataset.authenticated === "true";
}

function getUserTheme() {
  return document.body.dataset.userTheme || null;
}

function getThemeEndpoint() {
  return document.body.dataset.themeEndpoint || null;
}

function initTheme() {
  const userTheme = isAuthenticated() ? getUserTheme() : null;
  const stored = getStoredTheme();

  // Priority: the logged-in user's saved server-side theme first (so it
  // follows them to any browser/device), then whatever this browser had
  // saved locally (anonymous visitors, or before this account-level
  // feature existed), then the OS-level preference as a last resort.
  let theme;
  if (userTheme) {
    theme = userTheme;
  } else if (stored) {
    theme = stored;
  } else {
    // window.matchMedia lets JS check a CSS media query -- the same
    // prefers-color-scheme feature CSS itself can query.
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    theme = prefersDark ? "dark" : "light";
  }

  applyTheme(theme);

  const toggle = document.getElementById("dark-mode-toggle");
  if (toggle) {
    toggle.checked = theme === "dark";
  }
}

// Reads a cookie by name -- used to grab Django's csrftoken cookie so the
// fetch() call below can pass it back in the X-CSRFToken header, which
// CsrfViewMiddleware requires on POST requests made outside a normal
// <form> submission.
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

// Best-effort save to the server so a logged-in user's theme choice
// follows them across browsers/devices. If this fails (offline, session
// expired, etc.) the choice still applied locally via applyTheme() and
// localStorage above -- it just won't sync anywhere else until the next
// successful save.
function saveThemeToServer(theme) {
  const endpoint = getThemeEndpoint();
  if (!endpoint) return;

  fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: `theme=${encodeURIComponent(theme)}`,
  }).catch(() => {});
}

function initSettingsPanel() {
  const button = document.getElementById("settings-toggle");
  const panel = document.getElementById("settings-panel");
  const darkModeToggle = document.getElementById("dark-mode-toggle");
  if (!button || !panel) return;

  button.addEventListener("click", () => {
    const isOpen = !panel.hidden;
    panel.hidden = isOpen;
    // aria-expanded tells screen readers whether the button's popup is
    // currently open -- keeping it in sync with the actual state is what
    // makes this accessible, not just visually functional.
    button.setAttribute("aria-expanded", String(!isOpen));
  });

  // Close the panel on an outside click, so it doesn't stay open forever
  // once you've clicked away from it.
  document.addEventListener("click", (event) => {
    const clickedOutside = !panel.contains(event.target) && event.target !== button;
    if (!panel.hidden && clickedOutside) {
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
    }
  });

  if (darkModeToggle) {
    darkModeToggle.addEventListener("change", () => {
      const theme = darkModeToggle.checked ? "dark" : "light";
      applyTheme(theme);
      try {
        localStorage.setItem(THEME_KEY, theme);
      } catch (err) {
        // Preference just won't persist across reloads -- not worth
        // breaking the page over.
      }

      if (isAuthenticated()) {
        saveThemeToServer(theme);
      }
    });
  }
}

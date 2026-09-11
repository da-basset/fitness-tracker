// Runs on any page that renders the shared phase/week/day schedule +
// workout/exercise detail view: the client's own live Physical Training
// page, the trainer/owner's plan editor, and the read-only "Client view"
// preview / a client's own past-plan history page. All four share this
// one file; window.TRAINING_CONFIG (injected by each template via a small
// inline <script> before this one loads) says which mode we're in and
// supplies that mode's API URLs -- nothing here is hardcoded to one page
// anymore.
//
// Modes:
//   "client"  -- the client's own live tracking. Set-checkboxes, rest
//                timers, and "Mark Completed" are interactive. No
//                structure-editing controls (those moved to "trainer").
//   "trainer" -- trainer/owner editing one plan's Workouts/Phases content
//                at the exercise level (add/edit/delete/reorder). No
//                tracking controls at all -- editing plan structure isn't
//                the same thing as logging a workout.
//   "preview" / "history" -- read-only. Tracking controls render showing
//                the real current state but are disabled; nothing clicked
//                here is saved. "preview" is the trainer/owner "Client
//                view" button; "history" is a client's own past plan.
//   "workout"  -- trainer/owner editing a single workout's exercises from
//                the Workouts & Phases manager (no phase/week schedule
//                nav -- just that one workout's exercise table, add form,
//                edit, delete, and drag-reorder).
//
// Navigation is two levels in every mode: the top phase-tabs row picks a
// Phase (e.g. "Ramp-In"), then a second week-tabs row -- rendered inside
// the panel, since a phase's week count varies -- picks one of that
// phase's Weeks, each independently configurable with its own Mon-Sun
// schedule.
document.addEventListener("DOMContentLoaded", () => {
  const CONFIG = window.TRAINING_CONFIG || { mode: "client" };
  const MODE = CONFIG.mode || "client";
  const tabsEl = document.getElementById("phaseTabs");
  const workoutDetailEl = document.getElementById("workoutDetail");
  if (!tabsEl && !workoutDetailEl) return; // not on this page (schedule view or single-workout editor)

  const IS_EDITABLE = MODE === "trainer" || MODE === "workout"; // exercise add/edit/delete/reorder
  const SHOW_TRACKING = MODE !== "trainer" && MODE !== "workout"; // checkboxes/timer/complete render at all
  const TRACKING_INTERACTIVE = MODE === "client"; // ...and actually persist

  function fillId(template, id) {
    return (template || "").replace("__ID__", id);
  }
  const scheduleUrl = () => CONFIG.scheduleUrl;
  const workoutUrl = (id) => fillId(CONFIG.workoutUrlTemplate, id);
  const toggleSetApiUrl = (id, setNumber) => fillId(CONFIG.toggleSetUrlTemplate, id).replace("__SET__", setNumber);
  const completeApiUrl = (id) => fillId(CONFIG.completeUrlTemplate, id);
  const createExerciseApiUrl = (id) => fillId(CONFIG.createExerciseUrlTemplate, id);
  const reorderApiUrl = (id) => fillId(CONFIG.reorderUrlTemplate, id);
  const exerciseDetailApiUrl = (id) => fillId(CONFIG.exerciseDetailUrlTemplate, id);

  const dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const NUTRIENTS_TAB = "__nutrients__";
  const SUPPLEMENTS_TAB = "__supplements__";

  let schedule = null; // { workouts: {...}, phases: [...], nutrients: [...], supplements: [...] }
  let activeTab = null; // a phase id, or NUTRIENTS_TAB / SUPPLEMENTS_TAB
  let activeWeek = null;
  let selectedDay = null; // { dow, workoutId }
  let activeTimers = {}; // exerciseId -> interval id
  let completedByExercise = {}; // exerciseId -> Set of completed set numbers
  let requestToken = 0; // guards against a slow fetch clobbering a newer selection
  let dragArmed = false; // true only right after mousedown on a .exercise-drag-handle
  let draggingExerciseId = null; // exercise id currently being dragged, or null

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  async function apiFetch(url, options = {}) {
    const opts = Object.assign({ credentials: "same-origin" }, options);
    opts.headers = Object.assign({}, options.headers);
    if (options.method && options.method !== "GET") {
      opts.headers["X-CSRFToken"] = getCookie("csrftoken");
      if (options.body && !opts.headers["Content-Type"]) {
        opts.headers["Content-Type"] = "application/json";
      }
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = "";
      try {
        const data = await res.json();
        detail = data.error || "";
      } catch (err) {
        // response wasn't JSON -- fall back to the generic message below
      }
      throw new Error(detail || `Request failed (${res.status})`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  // Renders the "N/total this week" badge in the phase-head's upper-right
  // corner, swapping to a "Week Complete" stamp once the tally reaches
  // the phase's days-per-week. Shown in every mode when there's an owning
  // client to compute it for (a pure library template has none).
  function renderTallyInner(tally) {
    if (!tally || !tally.total) return "";
    if (tally.week_complete) {
      return `<span class="tally-stamp">&#10003; Week Complete</span>`;
    }
    return `<span class="tally-count">${tally.completed}/${tally.total} this week</span>`;
  }

  // Used when interpolating exercise field values into HTML attributes
  // (the edit form's pre-filled inputs) so a name/reps/etc containing a
  // quote or angle bracket can't break out of the attribute.
  function escapeAttr(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // A ringing-bell alert when a rest period finishes. Synthesized with
  // WebAudio: each strike layers a fundamental tone with a few
  // inharmonic overtones, each with a fast attack and long exponential
  // decay -- struck three times, fading, like a bell being rung.
  function playChime() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const now = ctx.currentTime;

      const fundamental = 880;
      const partials = [
        { ratio: 1, gain: 0.32 },
        { ratio: 2.41, gain: 0.16 },
        { ratio: 3.12, gain: 0.11 },
        { ratio: 4.47, gain: 0.06 }
      ];
      const decay = 1.1;
      const strikes = [
        { offset: 0, level: 1 },
        { offset: 0.45, level: 0.75 },
        { offset: 0.9, level: 0.55 }
      ];

      strikes.forEach((strike) => {
        const strikeTime = now + strike.offset;
        partials.forEach((p) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.value = fundamental * p.ratio;
          gain.gain.setValueAtTime(0.0001, strikeTime);
          gain.gain.linearRampToValueAtTime(p.gain * strike.level, strikeTime + 0.008);
          gain.gain.exponentialRampToValueAtTime(0.0001, strikeTime + decay);
          osc.connect(gain).connect(ctx.destination);
          osc.start(strikeTime);
          osc.stop(strikeTime + decay + 0.05);
        });
      });

      const lastStrike = strikes[strikes.length - 1].offset;
      setTimeout(() => ctx.close(), (lastStrike + decay + 0.2) * 1000);
    } catch (err) {
      // Audio unavailable/blocked -- not worth breaking the timer over.
    }
  }

  // Nutrients/Supplements are flat reference lists, not phases -- they
  // get two "virtual" tabs of their own, styled identically to a phase
  // tab (same .phase-tab class, same strip), placed first so they read
  // left-to-right in the order Isaac laid the plan out: Nutrients,
  // Supplements, then the actual training phases.
  function renderVirtualTab(key, label, count) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "phase-tab" + (key === activeTab ? " active" : "");
    // Same two-line shape as a phase tab (title + a smaller range/sub
    // line) so the strip lines up evenly -- a plain one-line label here
    // rendered visibly shorter than the phase tabs next to it.
    b.innerHTML = `${label}<span class="phase-tab-range">${count} item${count === 1 ? "" : "s"}</span>`;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", key === activeTab);
    b.onclick = () => {
      if (key === activeTab) return;
      activeTab = key;
      selectedDay = null;
      renderTabs();
      renderPanel();
    };
    tabsEl.appendChild(b);
  }

  function renderTabs() {
    tabsEl.innerHTML = "";
    renderVirtualTab(NUTRIENTS_TAB, "Nutrients", schedule.nutrients.length);
    renderVirtualTab(SUPPLEMENTS_TAB, "Supplements", schedule.supplements.length);
    schedule.phases.forEach((p) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "phase-tab" + (p.id === activeTab ? " active" : "");
      b.innerHTML = `${p.title}<span class="phase-tab-range">${p.label}</span>`;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", p.id === activeTab);
      b.onclick = () => {
        if (p.id === activeTab) return;
        activeTab = p.id;
        activeWeek = p.weeks.length ? p.weeks[0].id : null;
        selectedDay = null;
        renderTabs();
        renderPanel();
      };
      tabsEl.appendChild(b);
    });
  }

  // Second-level nav, rendered inside the phase panel (not the top tabs
  // row) since each phase can have a different number of weeks. Only
  // shown when the active phase has more than one week -- a single-week
  // phase just shows that week's grid directly.
  function renderWeekTabs(phase) {
    const wrap = document.createElement("nav");
    wrap.className = "week-tabs";
    wrap.setAttribute("role", "tablist");
    wrap.setAttribute("aria-label", `Weeks in ${phase.title}`);
    if (phase.weeks.length < 2) return wrap;
    phase.weeks.forEach((w) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "week-tab" + (w.id === activeWeek ? " active" : "");
      b.textContent = w.label;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", w.id === activeWeek);
      b.onclick = () => {
        if (w.id === activeWeek) return;
        activeWeek = w.id;
        selectedDay = null;
        renderPanel();
      };
      wrap.appendChild(b);
    });
    return wrap;
  }

  // Small inline icon buttons for the Actions column -- a pencil to open
  // the edit form below the row, a red trash can to remove the exercise
  // entirely, and a drag grip to reorder. Trainer/owner editing only --
  // in every other mode the actions cell renders empty (see
  // renderExerciseRow) so a client or preview viewer sees no editing
  // affordances at all.
  function exerciseActionsHtml(ex) {
    const dragHandle = `
      <button type="button" class="exercise-drag-handle" data-exercise="${ex.id}" aria-label="Drag to reorder ${ex.name}" title="Drag to reorder">
        <svg class="icon icon-grip" viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><circle cx="9" cy="6" r="1.4"></circle><circle cx="15" cy="6" r="1.4"></circle><circle cx="9" cy="12" r="1.4"></circle><circle cx="15" cy="12" r="1.4"></circle><circle cx="9" cy="18" r="1.4"></circle><circle cx="15" cy="18" r="1.4"></circle></svg>
      </button>`;
    const editBtn = `
      <button type="button" class="exercise-edit" data-exercise="${ex.id}" aria-expanded="false" aria-controls="edit-row-${ex.id}" aria-label="Edit ${ex.name}">
        <svg class="icon icon-pencil" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
      </button>`;
    const deleteBtn = `
      <button type="button" class="exercise-delete" data-exercise="${ex.id}" aria-label="Remove ${ex.name}">
        <svg class="icon icon-trash" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
      </button>`;
    return `<td class="ex-actions">${dragHandle}${editBtn}${deleteBtn}</td>`;
  }

  // Hidden-by-default row holding the "edit this exercise" form, pre-filled
  // with its current details. Sits right under the exercise's main row;
  // the pencil button in exerciseActionsHtml toggles it open. Trainer/
  // owner editing only.
  function editExerciseRowHtml(ex) {
    return `
      <tr class="edit-row" id="edit-row-${ex.id}" data-exercise="${ex.id}" hidden>
        <td colspan="7">
          <form class="edit-exercise-form" data-exercise="${ex.id}">
            <label class="field name">
              <span>Name</span>
              <input type="text" name="name" required maxlength="200" value="${escapeAttr(ex.name)}">
            </label>
            <label class="field">
              <span>Segment</span>
              <select name="segment">
                <option value="Main"${ex.segment === "Main" ? " selected" : ""}>Main</option>
                <option value="Core"${ex.segment === "Core" ? " selected" : ""}>Core</option>
                <option value="Cardio"${ex.segment === "Cardio" ? " selected" : ""}>Cardio</option>
                <option value="Stretch"${ex.segment === "Stretch" ? " selected" : ""}>Stretch</option>
              </select>
            </label>
            <label class="field narrow">
              <span>Sets</span>
              <input type="number" name="sets_count" min="1" max="20" value="${ex.sets_count || ""}">
            </label>
            <label class="field">
              <span>Reps</span>
              <input type="text" name="reps_text" maxlength="60" placeholder="e.g. 8-10" value="${escapeAttr(ex.reps_text || "")}">
            </label>
            <label class="field narrow">
              <span>Rest (sec)</span>
              <input type="number" name="rest_seconds" min="0" max="3600" value="${ex.rest_seconds || ""}">
            </label>
            <label class="field">
              <span>Est. time</span>
              <input type="text" name="time_text" maxlength="20" placeholder="e.g. ~5 min" value="${escapeAttr(ex.time_text || "")}">
            </label>
            <div class="edit-exercise-actions">
              <button type="submit" class="btn-primary">Save</button>
              <button type="button" class="btn-cancel-edit">Cancel</button>
            </div>
          </form>
          <div class="edit-exercise-error" hidden></div>
        </td>
      </tr>`;
  }

  function renderExerciseRow(ex) {
    const completedSets = completedByExercise[ex.id] || new Set();
    const actionsCell = IS_EDITABLE ? exerciseActionsHtml(ex) : `<td class="ex-actions"></td>`;
    const editRowHtml = IS_EDITABLE ? editExerciseRowHtml(ex) : "";

    if (IS_EDITABLE) {
      // Structure-editing surface: no set-checkboxes/timer here at all --
      // that's the client's own tracking, not plan content. The pencil
      // button (editRowHtml) is the only editing affordance for an
      // exercise's own fields; sets/reps/rest/time show as plain text.
      return `
        <tr class="exercise-main-row seg-${ex.segment}" data-exercise="${ex.id}" draggable="true">
          <td></td>
          <td><span class="seg-tag seg-${ex.segment}">${ex.segment}</span></td>
          <td class="ex-name">${ex.name}</td>
          <td>${ex.sets_reps_display}</td>
          <td>${ex.rest_display}</td>
          <td>${ex.time_text}</td>
          ${actionsCell}
        </tr>
        ${editRowHtml}`;
    }

    const disabledAttr = TRACKING_INTERACTIVE ? "" : "disabled";

    if (ex.sets_count) {
      const setChips = Array.from({ length: ex.sets_count }, (_, s) => {
        const setNumber = s + 1;
        const checked = completedSets.has(setNumber) ? "checked" : "";
        return `
          <label class="set-chip">
            <input type="checkbox" class="set-chk" data-exercise="${ex.id}" data-set="${setNumber}" data-rest="${ex.rest_seconds || 0}" ${checked} ${disabledAttr}>
            Set ${setNumber}
          </label>`;
      }).join("");

      const doneCount = completedSets.size;

      return `
        <tr class="exercise-main-row seg-${ex.segment}${doneCount === ex.sets_count ? " done" : ""}" data-exercise="${ex.id}">
          <td>
            <button type="button" class="set-toggle" data-exercise="${ex.id}" aria-expanded="false" aria-controls="set-row-${ex.id}" aria-label="Expand sets for ${ex.name}">&#9656;</button>
          </td>
          <td><span class="seg-tag seg-${ex.segment}">${ex.segment}</span></td>
          <td class="ex-name">${ex.name}<span class="set-progress" data-exercise="${ex.id}"> ${doneCount}/${ex.sets_count}</span></td>
          <td>${ex.sets_reps_display}</td>
          <td>${ex.rest_display}</td>
          <td>${ex.time_text}</td>
          ${actionsCell}
        </tr>
        ${editRowHtml}
        <tr class="set-row" id="set-row-${ex.id}" data-exercise="${ex.id}" hidden>
          <td colspan="7">
            <div class="set-panel">
              <div class="set-list">${setChips}</div>
              <div class="rest-timer" data-exercise="${ex.id}" hidden>
                <div class="rest-timer-bar"><div class="rest-timer-fill"></div></div>
                <span class="rest-timer-label"></span>
              </div>
            </div>
          </td>
        </tr>`;
    }

    const checked = completedSets.has(1) ? "checked" : "";
    return `
      <tr class="exercise-main-row seg-${ex.segment}${completedSets.has(1) ? " done" : ""}" data-exercise="${ex.id}">
        <td><input type="checkbox" class="chk" data-exercise="${ex.id}" aria-label="Mark ${ex.name} done" ${checked} ${disabledAttr}></td>
        <td><span class="seg-tag seg-${ex.segment}">${ex.segment}</span></td>
        <td class="ex-name">${ex.name}</td>
        <td>${ex.sets_reps_display}</td>
        <td>${ex.rest_display}</td>
        <td>${ex.time_text}</td>
        ${actionsCell}
      </tr>
      ${editRowHtml}`;
  }

  function updateSetProgress(container, exerciseId, setsCount) {
    const completedSets = completedByExercise[exerciseId] || new Set();
    const progressEl = container.querySelector(`.set-progress[data-exercise="${exerciseId}"]`);
    if (progressEl) progressEl.textContent = ` ${completedSets.size}/${setsCount}`;

    const exerciseRow = container.querySelector(`tr[data-exercise="${exerciseId}"]:not(.set-row):not(.edit-row)`);
    if (exerciseRow) {
      exerciseRow.classList.toggle("done", setsCount > 0 && completedSets.size === setsCount);
    }
  }

  function startRestTimer(container, exerciseId, restSeconds) {
    if (activeTimers[exerciseId]) {
      clearInterval(activeTimers[exerciseId]);
      delete activeTimers[exerciseId];
    }

    const timerEl = container.querySelector(`.rest-timer[data-exercise="${exerciseId}"]`);
    if (!timerEl) return;
    const fillEl = timerEl.querySelector(".rest-timer-fill");
    const labelEl = timerEl.querySelector(".rest-timer-label");

    let remaining = restSeconds;
    timerEl.hidden = false;
    timerEl.classList.remove("done");
    labelEl.textContent = `Rest: ${formatTime(remaining)}`;
    if (fillEl) fillEl.style.width = "100%";

    activeTimers[exerciseId] = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(activeTimers[exerciseId]);
        delete activeTimers[exerciseId];
        labelEl.textContent = "Rest complete";
        timerEl.classList.add("done");
        if (fillEl) fillEl.style.width = "0%";
        playChime();
        setTimeout(() => {
          timerEl.hidden = true;
          timerEl.classList.remove("done");
        }, 2500);
        return;
      }
      labelEl.textContent = `Rest: ${formatTime(remaining)}`;
      if (fillEl) fillEl.style.width = `${(remaining / restSeconds) * 100}%`;
    }, 1000);
  }

  function addExerciseFormHtml(workoutId) {
    // Only the standalone single-workout editor (workout_form.html, mode
    // "workout") has a name/sub/flavor/color form to save -- the trainer's
    // per-day exercise view on plan_detail.html (mode "trainer") also
    // renders through this same function but has no such form, so the
    // button is added here rather than unconditionally.
    const saveChangesBtn = MODE === "workout"
      ? `<button type="submit" form="workout-details-form" class="btn-primary">Save changes</button>`
      : "";
    return `
      <div class="edit-exercises">
        <div class="edit-exercises-toolbar">
          <button type="button" class="edit-exercises-toggle" id="edit-exercises-toggle" aria-expanded="false" aria-controls="add-exercise-form">
            <span class="edit-exercises-icon" aria-hidden="true">&#9656;</span>
            Add exercise
          </button>
          ${saveChangesBtn}
        </div>
        <form class="add-exercise-form" id="add-exercise-form" hidden data-workout="${workoutId}">
          <label class="field name">
            <span>Name</span>
            <input type="text" name="name" required maxlength="200">
          </label>
          <label class="field">
            <span>Segment</span>
            <select name="segment">
              <option value="Main">Main</option>
              <option value="Core">Core</option>
              <option value="Cardio">Cardio</option>
              <option value="Stretch">Stretch</option>
            </select>
          </label>
          <label class="field narrow">
            <span>Sets</span>
            <input type="number" name="sets_count" min="1" max="20">
          </label>
          <label class="field">
            <span>Reps</span>
            <input type="text" name="reps_text" maxlength="60" placeholder="e.g. 8-10">
          </label>
          <label class="field narrow">
            <span>Rest (sec)</span>
            <input type="number" name="rest_seconds" min="0" max="3600">
          </label>
          <label class="field">
            <span>Est. time</span>
            <input type="text" name="time_text" maxlength="20" placeholder="e.g. ~5 min">
          </label>
          <button type="submit" class="btn-primary">Add</button>
        </form>
        <div class="add-exercise-error" id="add-exercise-error" hidden></div>
      </div>`;
  }

  function wireDetailEvents(container, workoutId) {
    container.querySelectorAll(".set-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const exerciseId = btn.getAttribute("data-exercise");
        const setRow = container.querySelector(`.set-row[data-exercise="${exerciseId}"]`);
        const nowExpanded = btn.getAttribute("aria-expanded") !== "true";
        btn.setAttribute("aria-expanded", String(nowExpanded));
        btn.classList.toggle("expanded", nowExpanded);
        if (setRow) setRow.hidden = !nowExpanded;
      });
    });

    async function toggleSet(exerciseId, setNumber, checkboxEl) {
      const wasChecked = checkboxEl.checked;
      try {
        const result = await apiFetch(toggleSetApiUrl(exerciseId, setNumber), { method: "POST" });
        const set = completedByExercise[exerciseId] || (completedByExercise[exerciseId] = new Set());
        if (result.completed) set.add(setNumber); else set.delete(setNumber);
        return true;
      } catch (err) {
        checkboxEl.checked = !wasChecked; // revert the optimistic UI flip
        return false;
      }
    }

    if (TRACKING_INTERACTIVE) {
      container.querySelectorAll(".chk").forEach((box) => {
        box.addEventListener("change", async (e) => {
          const exerciseId = e.target.getAttribute("data-exercise");
          const ok = await toggleSet(exerciseId, 1, e.target);
          if (ok) {
            e.target.closest("tr").classList.toggle("done", e.target.checked);
          }
        });
      });

      container.querySelectorAll(".set-chk").forEach((box) => {
        box.addEventListener("change", async (e) => {
          const exerciseId = e.target.getAttribute("data-exercise");
          const setNumber = parseInt(e.target.getAttribute("data-set"), 10);
          const restSeconds = parseInt(e.target.getAttribute("data-rest"), 10) || 0;
          const wasChecked = e.target.checked;
          const ok = await toggleSet(exerciseId, setNumber, e.target);
          if (!ok) return;

          const setsCount = container.querySelectorAll(`.set-chk[data-exercise="${exerciseId}"]`).length;
          updateSetProgress(container, exerciseId, setsCount);
          if (wasChecked && restSeconds > 0) {
            startRestTimer(container, exerciseId, restSeconds);
          }
        });
      });
    }

    if (!IS_EDITABLE) return; // everything below is trainer/owner editing only

    container.querySelectorAll(".exercise-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const exerciseId = btn.getAttribute("data-exercise");
        const exerciseName = (btn.getAttribute("aria-label") || "").replace(/^Remove\s+/, "");
        if (!window.confirm(`Remove "${exerciseName}" from this workout? This can't be undone.`)) return;
        try {
          await apiFetch(exerciseDetailApiUrl(exerciseId), { method: "DELETE" });
          delete completedByExercise[exerciseId];
          if (activeTimers[exerciseId]) {
            clearInterval(activeTimers[exerciseId]);
            delete activeTimers[exerciseId];
          }
          const row = container.querySelector(`tr[data-exercise="${exerciseId}"]:not(.set-row):not(.edit-row)`);
          const setRow = container.querySelector(`.set-row[data-exercise="${exerciseId}"]`);
          const editRow = container.querySelector(`.edit-row[data-exercise="${exerciseId}"]`);
          if (row) row.remove();
          if (setRow) setRow.remove();
          if (editRow) editRow.remove();
        } catch (err) {
          // Leave the row in place -- nothing to recover visually, the
          // request simply didn't go through.
        }
      });
    });

    container.querySelectorAll(".exercise-edit").forEach((btn) => {
      wireExerciseEdit(container, btn.getAttribute("data-exercise"));
    });

    const toggleBtn = container.querySelector("#edit-exercises-toggle");
    const form = container.querySelector("#add-exercise-form");
    const errorEl = container.querySelector("#add-exercise-error");
    const logTable = container.querySelector("table.log");
    if (toggleBtn && form) {
      const closeEditPanel = () => {
        toggleBtn.setAttribute("aria-expanded", "false");
        toggleBtn.classList.remove("expanded");
        if (logTable) logTable.classList.remove("editing");
        form.hidden = true;
      };
      toggleBtn.addEventListener("click", () => {
        const nowExpanded = toggleBtn.getAttribute("aria-expanded") !== "true";
        toggleBtn.setAttribute("aria-expanded", String(nowExpanded));
        toggleBtn.classList.toggle("expanded", nowExpanded);
        if (logTable) logTable.classList.toggle("editing", nowExpanded);
        form.hidden = !nowExpanded;
      });
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        errorEl.hidden = true;
        const data = new FormData(form);
        const payload = {
          name: data.get("name"),
          segment: data.get("segment"),
          sets_count: data.get("sets_count") || null,
          reps_text: data.get("reps_text") || "",
          rest_seconds: data.get("rest_seconds") || null,
          time_text: data.get("time_text") || "",
        };
        try {
          const exercise = await apiFetch(createExerciseApiUrl(workoutId), {
            method: "POST",
            body: JSON.stringify(payload),
          });
          completedByExercise[exercise.id] = new Set();
          const tbody = container.querySelector("table.log tbody");
          tbody.insertAdjacentHTML("beforeend", renderExerciseRow(exercise));
          wireRow(container, exercise.id);
          form.reset();
          closeEditPanel();
        } catch (err) {
          errorEl.textContent = err.message || "Couldn't add that exercise.";
          errorEl.hidden = false;
        }
      });
    }
  }

  // Wires just one newly-inserted row (used after adding a custom
  // exercise, so we don't have to re-wire the whole table).
  function wireRow(container, exerciseId) {
    const scopeSelector = `[data-exercise="${exerciseId}"]`;
    const toggle = container.querySelector(`.set-toggle${scopeSelector}`);
    if (toggle) {
      toggle.addEventListener("click", () => {
        const setRow = container.querySelector(`.set-row${scopeSelector}`);
        const nowExpanded = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(nowExpanded));
        toggle.classList.toggle("expanded", nowExpanded);
        if (setRow) setRow.hidden = !nowExpanded;
      });
    }
    if (TRACKING_INTERACTIVE) {
      container.querySelectorAll(`.chk${scopeSelector}`).forEach((box) => {
        box.addEventListener("change", async (e) => {
          const ok = await (async () => {
            try {
              const result = await apiFetch(toggleSetApiUrl(exerciseId, 1), { method: "POST" });
              const set = completedByExercise[exerciseId] || (completedByExercise[exerciseId] = new Set());
              if (result.completed) set.add(1); else set.delete(1);
              return true;
            } catch (err) {
              e.target.checked = !e.target.checked;
              return false;
            }
          })();
          if (ok) e.target.closest("tr").classList.toggle("done", e.target.checked);
        });
      });
      container.querySelectorAll(`.set-chk${scopeSelector}`).forEach((box) => {
        box.addEventListener("change", async (e) => {
          const setNumber = parseInt(e.target.getAttribute("data-set"), 10);
          const restSeconds = parseInt(e.target.getAttribute("data-rest"), 10) || 0;
          const wasChecked = e.target.checked;
          try {
            const result = await apiFetch(toggleSetApiUrl(exerciseId, setNumber), { method: "POST" });
            const set = completedByExercise[exerciseId] || (completedByExercise[exerciseId] = new Set());
            if (result.completed) set.add(setNumber); else set.delete(setNumber);
          } catch (err) {
            e.target.checked = !wasChecked;
            return;
          }
          const setsCount = container.querySelectorAll(`.set-chk${scopeSelector}`).length;
          updateSetProgress(container, exerciseId, setsCount);
          if (wasChecked && restSeconds > 0) startRestTimer(container, exerciseId, restSeconds);
        });
      });
    }
    if (!IS_EDITABLE) return;
    const delBtn = container.querySelector(`.exercise-delete${scopeSelector}`);
    if (delBtn) {
      delBtn.addEventListener("click", async () => {
        const exerciseName = (delBtn.getAttribute("aria-label") || "").replace(/^Remove\s+/, "");
        if (!window.confirm(`Remove "${exerciseName}" from this workout? This can't be undone.`)) return;
        try {
          await apiFetch(exerciseDetailApiUrl(exerciseId), { method: "DELETE" });
          delete completedByExercise[exerciseId];
          if (activeTimers[exerciseId]) {
            clearInterval(activeTimers[exerciseId]);
            delete activeTimers[exerciseId];
          }
          const row = container.querySelector(`tr${scopeSelector}:not(.set-row):not(.edit-row)`);
          const setRow = container.querySelector(`.set-row${scopeSelector}`);
          const editRow = container.querySelector(`.edit-row${scopeSelector}`);
          if (row) row.remove();
          if (setRow) setRow.remove();
          if (editRow) editRow.remove();
        } catch (err) {
          // leave it in place
        }
      });
    }
    wireExerciseEdit(container, exerciseId);
  }

  // Wires the pencil button + its edit form for one exercise: toggling the
  // form open/closed, Cancel, and Save (PATCH the details, then swap in a
  // freshly-rendered row/edit-row/set-row group in place). Trainer/owner
  // editing only. Called both for the rows rendered on initial load and
  // for a row just added or edited.
  function wireExerciseEdit(container, exerciseId) {
    if (!IS_EDITABLE) return;
    const scopeSelector = `[data-exercise="${exerciseId}"]`;
    const editBtn = container.querySelector(`.exercise-edit${scopeSelector}`);
    const editRow = container.querySelector(`.edit-row${scopeSelector}`);
    if (!editBtn || !editRow) return;
    const form = editRow.querySelector(".edit-exercise-form");
    const errorEl = editRow.querySelector(".edit-exercise-error");
    const cancelBtn = editRow.querySelector(".btn-cancel-edit");

    const closeEdit = () => {
      editBtn.setAttribute("aria-expanded", "false");
      editBtn.classList.remove("expanded");
      editRow.hidden = true;
    };

    editBtn.addEventListener("click", () => {
      const nowExpanded = editBtn.getAttribute("aria-expanded") !== "true";
      editBtn.setAttribute("aria-expanded", String(nowExpanded));
      editBtn.classList.toggle("expanded", nowExpanded);
      editRow.hidden = !nowExpanded;
    });

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => closeEdit());
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorEl.hidden = true;
      const data = new FormData(form);
      const payload = {
        name: data.get("name"),
        segment: data.get("segment"),
        sets_count: data.get("sets_count") || null,
        reps_text: data.get("reps_text") || "",
        rest_seconds: data.get("rest_seconds") || null,
        time_text: data.get("time_text") || "",
      };
      try {
        const updated = await apiFetch(exerciseDetailApiUrl(exerciseId), {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        const tbody = container.querySelector("table.log tbody");
        const oldMain = container.querySelector(`tr${scopeSelector}:not(.set-row):not(.edit-row)`);
        const oldSetRow = container.querySelector(`.set-row${scopeSelector}`);
        const oldEditRow = container.querySelector(`.edit-row${scopeSelector}`);
        const anchor = (oldSetRow || oldEditRow || oldMain).nextSibling;
        [oldMain, oldEditRow, oldSetRow].forEach((el) => el && el.remove());
        const temp = document.createElement("tbody");
        temp.innerHTML = renderExerciseRow(updated);
        Array.from(temp.children).forEach((row) => tbody.insertBefore(row, anchor));
        wireRow(container, String(updated.id));
      } catch (err) {
        errorEl.textContent = err.message || "Couldn't save those changes.";
        errorEl.hidden = false;
      }
    });
  }

  // --- Drag-and-drop reordering (trainer/owner editing only) ---
  //
  // Each exercise is 2 sibling <tr>s in one shared <tbody> (the main row
  // and its hidden edit-row). The main row is draggable="true"; dragging
  // is only armed by a mousedown on its .exercise-drag-handle grip icon
  // (tracked via dragArmed) so grabbing the exercise name doesn't start a
  // drag. Everything below is wired once, globally, via event delegation,
  // so newly-added or freshly-edited rows work without any extra
  // re-wiring. None of this is registered at all outside trainer mode.

  function getExerciseRowGroup(tbody, exerciseId) {
    const scope = `[data-exercise="${exerciseId}"]`;
    const main = tbody.querySelector(`tr.exercise-main-row${scope}`);
    const editRow = tbody.querySelector(`tr.edit-row${scope}`);
    const setRow = tbody.querySelector(`tr.set-row${scope}`);
    return [main, editRow, setRow].filter(Boolean);
  }

  function clearDragOverIndicators(tbody) {
    tbody.querySelectorAll(".drag-over-top, .drag-over-bottom").forEach((el) => {
      el.classList.remove("drag-over-top", "drag-over-bottom");
    });
  }

  function moveExerciseGroup(tbody, draggedId, targetId, before) {
    const draggedRows = getExerciseRowGroup(tbody, draggedId);
    const targetRows = getExerciseRowGroup(tbody, targetId);
    if (!draggedRows.length || !targetRows.length) return;
    const anchorNode = before ? targetRows[0] : targetRows[targetRows.length - 1].nextSibling;
    draggedRows.forEach((row) => tbody.insertBefore(row, anchorNode));
  }

  async function persistExerciseOrder(table) {
    const workoutId = table.getAttribute("data-workout-id");
    const ids = Array.from(table.querySelectorAll("tbody tr.exercise-main-row")).map(
      (row) => row.getAttribute("data-exercise")
    );
    try {
      await apiFetch(reorderApiUrl(workoutId), {
        method: "POST",
        body: JSON.stringify({ order: ids }),
      });
    } catch (err) {
      // The reorder didn't stick server-side -- reload this workout's
      // detail panel so the UI matches what's actually saved.
      const detailEl = table.closest(".detail");
      if (detailEl) loadAndRenderDetail(detailEl, workoutId);
    }
  }

  if (IS_EDITABLE) {
    document.addEventListener("mousedown", (e) => {
      dragArmed = !!e.target.closest(".exercise-drag-handle");
    });

    document.addEventListener("mouseup", () => {
      dragArmed = false;
    });

    document.addEventListener("dragstart", (e) => {
      const row = e.target.closest("tr.exercise-main-row");
      if (!row || !dragArmed) {
        e.preventDefault();
        return;
      }
      dragArmed = false;
      draggingExerciseId = row.getAttribute("data-exercise");
      e.dataTransfer.effectAllowed = "move";
      try {
        e.dataTransfer.setData("text/plain", draggingExerciseId);
      } catch (err) {
        // Some browsers restrict setData outside a user gesture context --
        // harmless to skip, dataTransfer isn't otherwise relied on.
      }
      const tbody = row.closest("tbody");
      if (tbody) {
        getExerciseRowGroup(tbody, draggingExerciseId).forEach((el) => el.classList.add("dragging"));
      }
    });

    document.addEventListener("dragover", (e) => {
      if (!draggingExerciseId) return;
      const targetRow = e.target.closest("tr.exercise-main-row");
      if (!targetRow) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const tbody = targetRow.closest("tbody");
      if (!tbody) return;
      clearDragOverIndicators(tbody);
      if (targetRow.getAttribute("data-exercise") === draggingExerciseId) return;
      const rect = targetRow.getBoundingClientRect();
      const before = e.clientY - rect.top < rect.height / 2;
      targetRow.classList.add(before ? "drag-over-top" : "drag-over-bottom");
    });

    document.addEventListener("drop", (e) => {
      if (!draggingExerciseId) return;
      const targetRow = e.target.closest("tr.exercise-main-row");
      const tbody = targetRow && targetRow.closest("tbody");
      if (!tbody) {
        draggingExerciseId = null;
        return;
      }
      e.preventDefault();
      clearDragOverIndicators(tbody);
      const targetId = targetRow.getAttribute("data-exercise");
      const draggedId = draggingExerciseId;
      draggingExerciseId = null;
      if (targetId === draggedId) return;
      const rect = targetRow.getBoundingClientRect();
      const before = e.clientY - rect.top < rect.height / 2;
      moveExerciseGroup(tbody, draggedId, targetId, before);
      const table = tbody.closest("table.log");
      if (table) persistExerciseOrder(table);
    });

    document.addEventListener("dragend", (e) => {
      draggingExerciseId = null;
      dragArmed = false;
      document.querySelectorAll(".dragging").forEach((el) => el.classList.remove("dragging"));
      const tbody = e.target.closest("tr") && e.target.closest("tr").closest("tbody");
      if (tbody) clearDragOverIndicators(tbody);
      document.querySelectorAll(".drag-over-top, .drag-over-bottom").forEach((el) => {
        el.classList.remove("drag-over-top", "drag-over-bottom");
      });
    });
  }

  async function loadAndRenderDetail(detailEl, workoutId) {
    const myToken = ++requestToken;
    detailEl.className = "detail open";
    detailEl.innerHTML = `<p class="flavor">Loading…</p>`;

    let workout;
    try {
      workout = await apiFetch(workoutUrl(workoutId));
    } catch (err) {
      if (myToken !== requestToken) return;
      detailEl.innerHTML = `<p class="flavor">Couldn't load this workout. Try again in a moment.</p>`;
      return;
    }
    if (myToken !== requestToken) return; // a newer selection has since taken over

    completedByExercise = {};
    Object.entries(workout.completed).forEach(([exerciseId, sets]) => {
      completedByExercise[exerciseId] = new Set(sets);
    });

    let completeControlHtml = "";
    if (SHOW_TRACKING) {
      if (TRACKING_INTERACTIVE) {
        completeControlHtml = `
          <button type="button" class="workout-complete-btn${workout.workout_completed ? " done" : ""}" id="workoutCompleteBtn">
            ${workout.workout_completed ? "&#10003; Completed" : "Mark Completed"}
          </button>`;
      } else {
        completeControlHtml = `
          <span class="workout-complete-btn${workout.workout_completed ? " done" : ""}" aria-disabled="true">
            ${workout.workout_completed ? "&#10003; Completed" : "Not completed"}
          </span>`;
      }
    }

    detailEl.innerHTML = `
      <div class="detail-head">
        <div>
          <h3>${workout.name}</h3>
          <span class="dsub">${workout.sub}</span>
        </div>
        ${completeControlHtml}
      </div>
      <p class="flavor">${workout.flavor}</p>
      <table class="log" data-workout-id="${workoutId}">
        <thead><tr>
          <th></th><th>Segment</th><th>Exercise</th><th>Sets x Reps</th><th>Rest</th><th>Est. Time</th><th></th>
        </tr></thead>
        <tbody>
          ${workout.exercises.map((ex) => renderExerciseRow(ex)).join("")}
        </tbody>
      </table>
      ${IS_EDITABLE ? addExerciseFormHtml(workoutId) : ""}
    `;
    wireDetailEvents(detailEl, workoutId);
    if (TRACKING_INTERACTIVE) wireWorkoutCompleteButton(detailEl, workoutId);
  }

  // Wires the "Mark Completed" button in the detail header: toggles
  // today's WorkoutCompletion for this workout, then refreshes both the
  // button's own state and the phase-head tally badge from the response.
  // Client mode only -- preview/history render the same state as inert
  // text instead (see loadAndRenderDetail).
  function wireWorkoutCompleteButton(detailEl, workoutId) {
    const btn = detailEl.querySelector("#workoutCompleteBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const result = await apiFetch(completeApiUrl(workoutId), {
          method: "POST",
          body: JSON.stringify({ week_id: activeWeek }),
        });
        btn.classList.toggle("done", result.completed);
        btn.innerHTML = result.completed ? "&#10003; Completed" : "Mark Completed";
        if (result.week_tally) {
          const phase = schedule.phases.find((p) => p.id === activeTab);
          const week = phase && phase.weeks.find((w) => w.id === activeWeek);
          if (week) week.week_tally = result.week_tally;
          const tallyEl = document.getElementById("weekTally");
          if (tallyEl) {
            tallyEl.className = "week-tally" + (result.week_tally.week_complete ? " complete" : "");
            tallyEl.innerHTML = renderTallyInner(result.week_tally);
          }
        }
      } catch (err) {
        // Nothing persisted -- leave the button as it was.
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Renders the Nutrients/Supplements tab content: a card (same
  // .phase-panel container the phases use) holding a titled head plus a
  // plain list of read-only rows -- name, amount/dosage, timing, notes.
  // Adding/editing/deleting rows happens on the plan's Manage page
  // (same as Workouts/Phases); this view only ever displays them.
  function renderNotesPanel(panel, title, items) {
    const head = document.createElement("div");
    head.className = "phase-head";
    head.innerHTML = `
      <div class="phase-titles">
        <h2>${title}</h2>
        <span class="sub">${items.length} item${items.length === 1 ? "" : "s"}</span>
      </div>
    `;
    panel.appendChild(head);

    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "flavor";
      empty.textContent = "Nothing set yet.";
      panel.appendChild(empty);
      return;
    }

    const list = document.createElement("ul");
    list.className = "note-list";
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "note-item";
      li.innerHTML = `
        <div class="note-item-head">
          <strong>${item.name}</strong>
          ${item.amount ? `<span class="note-item-amount">${item.amount}</span>` : ""}
        </div>
        ${item.timing ? `<div class="note-item-sub">${item.timing}</div>` : ""}
        ${item.notes ? `<div class="note-item-notes">${item.notes}</div>` : ""}
      `;
      list.appendChild(li);
    });
    panel.appendChild(list);
  }

  function renderPanel() {
    Object.keys(activeTimers).forEach((k) => clearInterval(activeTimers[k]));
    activeTimers = {};

    const panel = document.getElementById("phasePanel");
    panel.innerHTML = "";

    if (activeTab === NUTRIENTS_TAB) {
      renderNotesPanel(panel, "Nutrients", schedule.nutrients);
      return;
    }
    if (activeTab === SUPPLEMENTS_TAB) {
      renderNotesPanel(panel, "Supplements", schedule.supplements);
      return;
    }

    const phase = schedule.phases.find((p) => p.id === activeTab);

    if (!phase || !phase.weeks.length) {
      panel.innerHTML = `<p class="flavor">This phase has no weeks configured yet.</p>`;
      return;
    }
    const week = phase.weeks.find((w) => w.id === activeWeek) || phase.weeks[0];
    activeWeek = week.id;

    const head = document.createElement("div");
    head.className = "phase-head";
    head.innerHTML = `
      <div class="stamp">Phase ${phase.number}</div>
      <div class="phase-titles">
        <h2>${phase.title}</h2>
        <span class="sub">${phase.label} &middot; ${week.sub}</span>
      </div>
      <div class="week-tally${week.week_tally && week.week_tally.week_complete ? " complete" : ""}" id="weekTally">
        ${renderTallyInner(week.week_tally)}
      </div>
    `;
    panel.appendChild(head);

    const note = document.createElement("div");
    note.className = "phase-note";
    note.innerHTML = phase.note;
    panel.appendChild(note);

    if (!IS_EDITABLE) {
      const notes = document.createElement("div");
      notes.className = "phase-note";
      notes.innerHTML = `
        <strong>Notes:</strong> Back off if you notice:
        <ul>
          <li>Joint soreness (especially knees/ankles) lingering more than 48 hours</li>
          <li>Sharp or pinching joint pain -- different from normal muscle soreness</li>
          <li>Declining sleep quality or persistently low energy</li>
          <li>Performance dropping across several sessions in a row, not just one off day</li>
        </ul>
      `;
      panel.appendChild(notes);
    }

    panel.appendChild(renderWeekTabs(phase));

    const grid = document.createElement("div");
    grid.className = "week-grid";
    dow.forEach((d) => {
      const cell = document.createElement("div");
      cell.className = "day-cell";
      const label = document.createElement("span");
      label.className = "dow";
      label.textContent = d;
      cell.appendChild(label);

      const workoutId = week.days[d];
      if (workoutId) {
        const workout = schedule.workouts[workoutId];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "day-btn badge-" + workout.color + (selectedDay && selectedDay.dow === d ? " selected" : "");
        btn.textContent = workout.name;
        btn.onclick = () => {
          selectedDay = selectedDay && selectedDay.dow === d ? null : { dow: d, workoutId };
          renderPanel();
        };
        cell.appendChild(btn);
      } else {
        const rest = document.createElement("div");
        rest.className = "rest-cell";
        rest.textContent = "Rest";
        cell.appendChild(rest);
      }
      grid.appendChild(cell);
    });
    panel.appendChild(grid);

    const detail = document.createElement("div");
    detail.className = "detail";
    panel.appendChild(detail);

    if (selectedDay) {
      loadAndRenderDetail(detail, selectedDay.workoutId);
    }
  }

  async function init() {
    try {
      schedule = await apiFetch(scheduleUrl());
    } catch (err) {
      tabsEl.innerHTML = "";
      document.getElementById("phasePanel").innerHTML = `<p class="flavor">Couldn't load the training schedule. Try refreshing.</p>`;
      return;
    }
    // Nutrients/Supplements are always available as tabs even when the
    // plan has no phases configured yet -- default there instead of
    // bailing out, since there's still something to show.
    if (schedule.phases.length) {
      activeTab = schedule.phases[0].id;
      activeWeek = schedule.phases[0].weeks.length ? schedule.phases[0].weeks[0].id : null;
    } else {
      activeTab = NUTRIENTS_TAB;
      activeWeek = null;
    }
    renderTabs();
    renderPanel();
  }

  if (MODE === "workout") {
    // Single-workout exercise editor (Manage Workouts' per-workout edit
    // page) -- no phase/week schedule at all, just this one workout's
    // exercise table, reusing the exact same detail-rendering/editing code
    // the trainer's full plan schedule uses.
    if (workoutDetailEl) loadAndRenderDetail(workoutDetailEl, CONFIG.workoutId);
  } else {
    init();
  }
});

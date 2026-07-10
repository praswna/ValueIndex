// Plotly chart chrome — a faithful port of webui.base_layout and helpers.
// Colors come from registry.json at call sites; nothing hardcoded but chrome.

const FONT = 'system-ui, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif';

// Effective theme: the nav toggle stamps <html data-theme>; otherwise follow
// the system. data.js swaps registry.chrome for registry.chrome_dark when
// dark, so all chrome lookups below stay theme-correct.
export function isDark() {
  const t = document.documentElement.getAttribute("data-theme");
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function baseLayout(registry, overrides = {}, height = 420) {
  const chrome = registry.chrome;
  return Object.assign(
    {
      height,
      margin: { l: 50, r: 10, t: 30, b: 40 },
      plot_bgcolor: chrome.plot_bg,
      paper_bgcolor: "rgba(0,0,0,0)",
      font: { family: FONT, color: chrome.ink },
      hovermode: "x unified",
      legend: { orientation: "h", yanchor: "bottom", y: 1.02, x: 0 },
      xaxis: {
        showgrid: false, linecolor: chrome.axis_line, ticks: "outside",
        tickcolor: chrome.grid,
      },
      yaxis: {
        gridcolor: chrome.grid, zerolinecolor: chrome.axis_line,
        linecolor: "rgba(0,0,0,0)",
      },
    },
    overrides
  );
}

export const CONFIG = { responsive: true, displayModeBar: false, scrollZoom: false };

// Touch scrubbing: dragging a finger horizontally across a time-series chart
// moves the crosshair and live-updates the unified tooltip (vertical drags
// still scroll the page thanks to touch-action: pan-y). Desktop mice already
// get live hover on move, so this only handles touch/pen.
function attachScrub(el) {
  if (el._viScrub) return;
  el._viScrub = true;

  // Anchor on the longest visible trace; precompute its x values on the
  // axis' internal (numeric) scale so each scrub is a cheap binary search.
  let anchor = null;
  const prepare = () => {
    const fl = el._fullLayout;
    if (!fl || !fl.xaxis || !el.data) return null;
    let best = -1, bestLen = 0;
    el.data.forEach((tr, i) => {
      if (tr.visible === false || !tr.x || tr.hoverinfo === "skip") return;
      if (tr.x.length > bestLen) { best = i; bestLen = tr.x.length; }
    });
    if (best < 0) return null;
    const ms = Array.from(el.data[best].x, (v) => fl.xaxis.d2c(v));
    return { curve: best, ms };
  };

  let raf = null;
  const scrubAt = (clientX) => {
    const fl = el._fullLayout;
    if (!fl || !fl.xaxis || !fl._size) return;
    if (!anchor) anchor = prepare();
    if (!anchor || !anchor.ms.length) return;
    const px = clientX - el.getBoundingClientRect().left - fl._size.l;
    if (px < -8 || px > fl._size.w + 8) return;
    const target = fl.xaxis.p2c(Math.max(0, Math.min(fl._size.w, px)));
    if (target === undefined || target === null || Number.isNaN(target)) return;
    // binary search for the nearest data point
    const a = anchor.ms;
    let lo = 0, hi = a.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (a[mid] < target) lo = mid; else hi = mid;
    }
    const i = Math.abs(a[lo] - target) <= Math.abs(a[hi] - target) ? lo : hi;
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      try {
        Plotly.Fx.hover(el, [{ curveNumber: anchor.curve, pointNumber: i }]);
      } catch { /* chart mid-relayout */ }
    });
  };

  // Raw touch events with manual gesture arbitration: mobile browsers stop
  // streaming pointermove once they claim a pan, so we decide ourselves —
  // a horizontal-first drag becomes a scrub (preventDefault keeps the events
  // coming), a vertical-first drag is released to the page scroll.
  // Capture phase, because Plotly's drag layer swallows touches over the
  // plot area (stopPropagation) — bubbling listeners only ever fired on the
  // thin axis strip below it.
  let gesture = null; // { sx, sy, claimed }
  el.addEventListener("touchstart", (ev) => {
    const t = ev.touches[0];
    gesture = { sx: t.clientX, sy: t.clientY, claimed: false };
    // Own the whole touch interaction: Plotly's own touch handling both
    // duplicates the tap-tooltip (ours below) and hides hover during moves.
    ev.stopPropagation();
    scrubAt(t.clientX);
  }, { passive: true, capture: true });
  el.addEventListener("touchmove", (ev) => {
    if (!gesture) return;
    const t = ev.touches[0];
    if (!gesture.claimed) {
      const dx = Math.abs(t.clientX - gesture.sx);
      const dy = Math.abs(t.clientY - gesture.sy);
      if (dx < 6 && dy < 6) return;      // direction not decided yet
      if (dx <= dy) { gesture = null; return; }  // vertical -> page scrolls
      gesture.claimed = true;            // horizontal -> scrub
    }
    if (ev.cancelable) ev.preventDefault();
    // Once claimed, starve Plotly's own drag handlers — they treat the move
    // as a drag and hide the hover label we're driving.
    ev.stopPropagation();
    scrubAt(t.clientX);
  }, { passive: false, capture: true });
  el.addEventListener("touchend", (ev) => {
    if (gesture && gesture.claimed) ev.stopPropagation();
    gesture = null;
  }, { capture: true });
  el.addEventListener("touchcancel", () => { gesture = null; }, { capture: true });
  if (el.on) el.on("plotly_afterplot", () => { anchor = null; });
}

// Mobile-friendly render: lock every axis (fixedrange) and disable drag so a
// touch on the chart scrolls the page instead of zooming/panning. Tooltips
// (hover/tap) still work, and x-hover charts get touch scrubbing.
export function render(el, traces, layout) {
  const lay = { ...layout, dragmode: false };
  lay.xaxis = { ...(lay.xaxis || {}), fixedrange: true };
  lay.yaxis = { ...(lay.yaxis || {}), fixedrange: true };
  for (const k of Object.keys(lay)) {
    if (/^[xy]axis\d+$/.test(k)) lay[k] = { ...lay[k], fixedrange: true };
  }
  const p = Plotly.newPlot(el, traces, lay, CONFIG);
  const hm = lay.hovermode === undefined ? "x unified" : lay.hovermode;
  if (typeof hm === "string" && hm.startsWith("x")) p.then(() => attachScrub(el));
  return p;
}

export function lineTrace(dates, values, name, color, extra = {}) {
  return Object.assign(
    { x: dates, y: values, mode: "lines", name, line: { color, width: 2 } },
    extra
  );
}

// Recession shading as layout shapes (port of add_recession_shading).
export function recessionShapes(registry, ranges, startDate = null) {
  return ranges
    .filter(([, end]) => !startDate || end >= startDate)
    .map(([x0, x1]) => ({
      type: "rect", xref: "x", yref: "paper",
      x0: startDate && x0 < startDate ? startDate : x0, x1,
      y0: 0, y1: 1,
      fillcolor: registry.chrome.recession_fill,
      line: { width: 0 }, layer: "below",
    }));
}

export function hline(y, color, dash = "dot", width = 1) {
  return {
    type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: y, y1: y,
    line: { color, width, dash },
  };
}

export function ratingOf(registry, z) {
  for (const band of registry.ratings) {
    if (band.max_z === null || z <= band.max_z) return band;
  }
  return registry.ratings[registry.ratings.length - 1];
}

export function ratingBadge(registry, ratingKey) {
  const band = registry.ratings.find((r) => r.key === ratingKey);
  return `<span class="badge" style="background:${band.color}">${band.label_ko}</span>`;
}

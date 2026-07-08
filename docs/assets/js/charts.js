// Plotly chart chrome — a faithful port of webui.base_layout and helpers.
// Colors come from registry.json at call sites; nothing hardcoded but chrome.

const FONT = 'system-ui, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif';

export function baseLayout(registry, overrides = {}, height = 420) {
  const chrome = registry.chrome;
  return Object.assign(
    {
      height,
      margin: { l: 50, r: 10, t: 30, b: 40 },
      plot_bgcolor: "#ffffff",
      paper_bgcolor: "rgba(0,0,0,0)",
      font: { family: FONT, color: "#0b0b0b" },
      hovermode: "x unified",
      legend: { orientation: "h", yanchor: "bottom", y: 1.02, x: 0 },
      xaxis: {
        showgrid: false, linecolor: "#c3c2b7", ticks: "outside",
        tickcolor: chrome.grid,
      },
      yaxis: {
        gridcolor: chrome.grid, zerolinecolor: "#c3c2b7",
        linecolor: "rgba(0,0,0,0)",
      },
    },
    overrides
  );
}

export const CONFIG = { responsive: true, displayModeBar: false };

export function render(el, traces, layout) {
  return Plotly.newPlot(el, traces, layout, CONFIG);
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

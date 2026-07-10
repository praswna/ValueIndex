// Data loading + formatting. meta.json is fetched no-store first; every
// other file gets ?v=<generated_at> so daily updates bust the Pages cache.

import { isDark } from "./charts.js";

let _meta = null;

export async function loadMeta() {
  if (!_meta) {
    const resp = await fetch("data/meta.json", { cache: "no-store" });
    _meta = await resp.json();
  }
  return _meta;
}

export async function load(...names) {
  const meta = await loadMeta();
  const v = encodeURIComponent(meta.generated_at);
  const out = { meta };
  await Promise.all(
    names.map(async (name) => {
      const resp = await fetch(`data/${name}.json?v=${v}`);
      if (!resp.ok) throw new Error(`data/${name}.json: HTTP ${resp.status}`);
      out[name] = await resp.json();
    })
  );
  // In dark mode, swap the chart chrome so every registry.chrome.* lookup
  // (grid, axis_line, plot_bg, …) is theme-correct without touching pages.
  if (out.registry && out.registry.chrome_dark && isDark()) {
    out.registry.chrome = out.registry.chrome_dark;
  }
  return out;
}

// Format a value per the registry's unit decimal spec.
export function fmt(value, unit, registry) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const dec = registry.unit_decimals[unit] ?? 2;
  return Number(value).toLocaleString("ko-KR", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
}

export function fmtSigned(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const s = Number(value).toFixed(decimals);
  return value > 0 ? `+${s}` : s;
}

export function ym(dateStr) {
  return dateStr ? dateStr.slice(0, 7) : "-";
}

// 지표 상세: 타일 한 화면 + 탭하면 딥다이브 팝업 (공용 valpop 사용).
// summary 페이지가 detail.html#cape 처럼 해시로 특정 지표를 바로 열 수 있다.

import { load, fmt } from "../data.js";
import { injectNav, injectFooter } from "../nav.js";
import { showValuationPopup } from "../valpop.js";

injectNav();
const { meta, registry, panel, overview } = await load("registry", "panel", "overview");
injectFooter(meta, registry);

const ratingColor = (key) =>
  (registry.ratings.find((r) => r.key === key) || {}).color || "#898781";

document.getElementById("tiles").innerHTML =
  registry.valuation_keys.map((key) => {
    const m = registry.indicators[key];
    const s = overview.summaries[key];
    return `<button class="tile" data-key="${key}">
      <span class="tile-dot" style="background:${ratingColor(s.rating)}"></span>
      <span class="tile-label">${m.label_ko}</span>
      <span class="tile-value">${fmt(s.current, m.unit, registry)}</span>
      <span class="tile-sub">${m.unit} · 백분위 ${s.aligned_pctile.toFixed(0)}</span>
    </button>`;
  }).join("");

const show = (key) => showValuationPopup(registry, overview, key, () => panel);

document.getElementById("tiles").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile");
  if (tile) show(tile.dataset.key);
});

// deep link: detail.html#cape opens that indicator's popup right away
const hashKey = decodeURIComponent(location.hash.slice(1));
if (registry.valuation_keys.includes(hashKey)) show(hashKey);

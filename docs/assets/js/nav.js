// Shared header nav + footer, injected on every page.

const PAGES = [
  ["index.html", "📊 개요"],
  ["compare.html", "📈 비교"],
  ["detail.html", "🔍 상세"],
  ["thermometer.html", "🌡️ 온도계"],
  ["korea.html", "🇰🇷 한국"],
  ["cadence.html", "⏱️ 주기별"],
  ["guide.html", "📚 가이드"],
  ["start.html", "🧭 시작"],
  ["discipline.html", "🧘 규율"],
  ["lab.html", "🔬 실험실"],
];

export function injectNav() {
  const current = location.pathname.split("/").pop() || "index.html";
  const nav = document.createElement("nav");
  nav.className = "vi-nav";
  nav.innerHTML = `<div class="vi-nav-inner">
    <span class="vi-brand">ValueIndex</span>
    ${PAGES.map(
      ([href, label]) =>
        `<a href="${href}"${href === current ? ' class="active"' : ""}>${label}</a>`
    ).join("")}
  </div>`;
  document.body.prepend(nav);
}

export function injectFooter(meta, registry) {
  const f = document.createElement("footer");
  f.className = "vi";
  const when = meta.generated_at.replace("T", " ").replace("Z", " UTC");
  f.innerHTML = `데이터 생성: ${when} · 매일 아침 자동 갱신 · ${registry.disclaimer}`;
  document.body.appendChild(f);
}

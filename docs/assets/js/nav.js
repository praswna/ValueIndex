// Shared header nav + footer, injected on every page.

const PAGES = [
  ["index.html", "요약"],
  ["thermometer.html", "온도계"],
  ["korea.html", "한국"],
  ["whales.html", "큰손"],
  ["signals.html", "단기"],
  ["report.html", "월간점검"],
  ["guide.html", "가이드"],
  ["start.html", "시작"],
  ["discipline.html", "규율"],
];

function effectiveTheme() {
  const t = document.documentElement.getAttribute("data-theme");
  if (t === "dark" || t === "light") return t;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function injectNav() {
  const current = location.pathname.split("/").pop() || "index.html";
  const nav = document.createElement("nav");
  nav.className = "vi-nav";
  nav.innerHTML = `<div class="vi-nav-inner">
    ${PAGES.map(
      ([href, label]) =>
        `<a href="${href}"${href === current ? ' class="active"' : ""}>${label}</a>`
    ).join("")}
    <a href="#" id="vi-theme" title="라이트/다크 전환">${
      effectiveTheme() === "dark" ? "☀️" : "🌙"}</a>
  </div>`;
  document.body.prepend(nav);
  nav.querySelector("#vi-theme").addEventListener("click", (e) => {
    e.preventDefault();
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    try { localStorage.setItem("vi-theme", next); } catch { /* private mode */ }
    document.documentElement.setAttribute("data-theme", next);
    location.reload(); // charts pick up the new chrome on re-render
  });
}

export function injectFooter(meta, registry) {
  const f = document.createElement("footer");
  f.className = "vi";
  const when = meta.generated_at.replace("T", " ").replace("Z", " UTC");
  f.innerHTML = `데이터 생성: ${when} · 매일 아침 자동 갱신 · ${registry.disclaimer}`;
  document.body.appendChild(f);
}

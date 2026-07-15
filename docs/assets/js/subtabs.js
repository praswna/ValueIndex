// In-page sub-tabs: a pill row that shows one section at a time.
// Hash-addressable (page.html#tabId) so sub-tabs can be deep-linked,
// and a resize event is fired on switch so Plotly charts re-measure.

export function initSubtabs(barId, tabs) {
  const bar = document.getElementById(barId);
  const sections = tabs.map((t) => document.getElementById(t.section));

  function select(id, pushHash = true) {
    tabs.forEach((t, i) => {
      const on = t.id === id;
      sections[i].hidden = !on;
      bar.querySelector(`[data-tab="${t.id}"]`).classList.toggle("active", on);
    });
    if (pushHash) history.replaceState(null, "", "#" + id);
    window.dispatchEvent(new Event("resize"));
  }

  bar.innerHTML = tabs.map((t) =>
    `<button class="vi-btn" data-tab="${t.id}">${t.label}</button>`).join("");
  bar.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-tab]");
    if (btn) select(btn.dataset.tab);
  });

  const initial = tabs.find((t) => t.id === location.hash.slice(1)) || tabs[0];
  select(initial.id, location.hash.slice(1) === initial.id);

  // hash-only navigation (link to page.html#tab from the same page, or the
  // back button) doesn't reload the document — follow it here.
  window.addEventListener("hashchange", () => {
    const t = tabs.find((x) => x.id === location.hash.slice(1));
    if (t) select(t.id, false);
  });
  return select;
}

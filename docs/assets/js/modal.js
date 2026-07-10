// Shared tap-for-detail popup for tile pages (summary/whales/detail/…).
// The overlay is created once, lazily; pages just call openModal(html) and
// then render any charts into elements inside it.

let overlay = null;

function ensure() {
  if (overlay) return;
  overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="modal modal-lg" role="dialog" aria-modal="true">
      <button class="modal-close" aria-label="닫기">✕</button>
      <div class="modal-body"></div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector(".modal-close").addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
}

export function openModal(html) {
  ensure();
  overlay.querySelector(".modal-body").innerHTML = html;
  overlay.hidden = false;
  document.body.style.overflow = "hidden";
}

export function closeModal() {
  if (!overlay) return;
  overlay.hidden = true;
  document.body.style.overflow = "";
}

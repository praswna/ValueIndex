"""ValueIndex 로컬 데이터 수집기 — 순수 Tkinter GUI.

Streamlit·브라우저·이메일 입력 없이 창 하나로 동작합니다 (Tkinter는 파이썬
표준 라이브러리). 집(주거용) IP에서 실행하면 데이터센터 IP가 막히는 소스
(KRX·FINRA·AAII·SEC EDGAR 큰손)까지 수집됩니다.

    python collector_gui.py

버튼 3개를 순서대로 누르면 됩니다:
  ① 전체 수집   — 모든 소스를 실시간 수집해 sample_data/에 저장
  ② 사이트 재생성 — docs/data/*.json 다시 굽기
  ③ 커밋 & 푸시  — 저장소에 올리면 GitHub Pages가 1~2분 뒤 자동 배포
"""
from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import scrolledtext, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from valueindex import collect  # noqa: E402


class CollectorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.busy = False

        root.title("🛰️ ValueIndex 로컬 데이터 수집기")
        root.geometry("760x540")
        root.minsize(560, 400)

        bar = ttk.Frame(root, padding=(10, 10, 10, 4))
        bar.pack(fill="x")
        self.buttons = [
            ttk.Button(bar, text="①  전체 수집", command=self.on_collect),
            ttk.Button(bar, text="②  사이트 재생성", command=self.on_build),
            ttk.Button(bar, text="③  커밋 & 푸시", command=self.on_push),
        ]
        for b in self.buttons:
            b.pack(side="left", padx=4)

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(2, 6))

        self.log_widget = scrolledtext.ScrolledText(
            root, height=22, wrap="word", state="disabled",
            font=("Consolas", 10) if sys.platform.startswith("win") else ("Menlo", 11),
        )
        self.log_widget.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.log("집(주거용) IP에서 실행하면 KRX·FINRA·AAII·SEC EDGAR까지 수집됩니다.")
        self.log("① 전체 수집 → ② 사이트 재생성 → ③ 커밋 & 푸시 순서로 눌러 주세요.\n")
        self.root.after(100, self._drain)

    # ---- thread-safe UI updates via a queue ----
    def log(self, text: str) -> None:
        self.q.put(("log", text))

    def set_progress(self, i: int, n: int) -> None:
        self.q.put(("progress", (i, n)))

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log_widget.configure(state="normal")
                    self.log_widget.insert("end", payload + "\n")
                    self.log_widget.see("end")
                    self.log_widget.configure(state="disabled")
                elif kind == "progress":
                    i, n = payload
                    self.progress["maximum"] = n
                    self.progress["value"] = i
                elif kind == "done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for b in self.buttons:
            b.configure(state="disabled" if busy else "normal")

    def _run(self, job) -> None:
        if self.busy:
            return
        self._set_busy(True)

        def worker():
            try:
                job()
            except Exception as exc:  # noqa: BLE001 - surface everything to the log
                self.log(f"[오류] {type(exc).__name__}: {exc}")
            finally:
                self.q.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    # ---- button actions ----
    def on_collect(self) -> None:
        def job():
            self.log("=== ① 전체 수집 시작 ===")
            r = collect.collect_all(log=self.log, on_progress=self.set_progress)
            msg = f"\n완료: {len(r['ok'])}/{r['total']} 성공"
            if r["failed"]:
                msg += f" · 실패(기존 파일 유지): {', '.join(r['failed'])}"
            self.log(msg + "\n")
        self._run(job)

    def on_build(self) -> None:
        def job():
            self.log("=== ② 사이트 데이터 재생성 ===")
            collect.rebuild_site(log=self.log)
            self.log("")
        self._run(job)

    def on_push(self) -> None:
        def job():
            self.log("=== ③ 커밋 & 푸시 ===")
            ok = collect.git_publish(log=self.log)
            self.log("푸시 완료 ✓ (1~2분 뒤 GitHub Pages 반영)" if ok
                     else "푸시 실패 — 위 로그를 확인하세요." )
            self.log("")
        self._run(job)


def main() -> None:
    root = tk.Tk()
    CollectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

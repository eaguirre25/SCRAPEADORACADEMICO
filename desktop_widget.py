#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import textwrap
import tkinter as tk
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox


REPO_ROOT = Path(__file__).resolve().parent
OWNER = "eaguirre25"
REPO = "SCRAPEADORACADEMICO"
WORKFLOWS = [
    ("Scraper", "daily-scraper.yml"),
    ("Corpus", "extract_corpus (6).yml"),
    ("STM", "stm_analysis.yml"),
    ("Dashboard", "dashboard (2).yml"),
]
REFRESH_MS = 10 * 60 * 1000
WINDOW_WIDTH = 430
WINDOW_HEIGHT = 760


def run_command(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def github_token() -> str:
    try:
        output = run_command(["git", "credential", "fill"], "protocol=https\nhost=github.com\n\n")
    except Exception:
        return ""
    for line in output.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def github_json(url: str) -> dict:
    token = github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "scrapeadoracademico-desktop-widget",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def local_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value[:16]


def compact_authors(value: str) -> str:
    authors = [item.strip() for item in (value or "").split(";") if item.strip()]
    if not authors:
        return "Sin autor"
    if len(authors) > 2:
        return f"{authors[0]} et al."
    return " · ".join(authors)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_articles() -> list[dict[str, str]]:
    rows = read_csv_rows(REPO_ROOT / "data" / "master_records.csv")
    rows.sort(
        key=lambda row: (
            row.get("first_seen_date", ""),
            row.get("publication_date", ""),
            row.get("publication_year", ""),
            row.get("title", ""),
        ),
        reverse=True,
    )
    return rows[:10]


def stm_topics() -> list[dict[str, str]]:
    rows = read_csv_rows(REPO_ROOT / "output" / "tabla_topicos.csv")
    def prevalence(row: dict[str, str]) -> float:
        try:
            return float(str(row.get("prevalencia", "0")).replace(",", "."))
        except ValueError:
            return 0.0

    rows.sort(key=prevalence, reverse=True)
    return rows[:5]


def local_counts() -> dict[str, int]:
    data = REPO_ROOT / "data"
    return {
        "validados": len(read_csv_rows(data / "master_records.csv")),
        "revision": len(read_csv_rows(data / "review_records.csv")),
        "rechazados": len(read_csv_rows(data / "rejected_records.csv")),
    }


def workflow_runs() -> list[dict[str, str]]:
    runs: list[dict[str, str]] = []
    for label, workflow in WORKFLOWS:
        encoded = workflow.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{encoded}/runs?per_page=1"
        try:
            data = github_json(url)
            run = (data.get("workflow_runs") or [{}])[0]
            runs.append(
                {
                    "label": label,
                    "status": run.get("status") or "-",
                    "conclusion": run.get("conclusion") or "",
                    "updated_at": local_time(run.get("updated_at")),
                    "url": run.get("html_url") or "",
                }
            )
        except Exception as exc:
            runs.append({"label": label, "status": "sin datos", "conclusion": str(exc), "updated_at": "-", "url": ""})
    return runs


class Widget(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SCRAPEADORACADEMICO")
        self.configure(bg="#0d1117")
        self.place_on_screen()
        self.minsize(390, 620)
        self.attributes("-topmost", True)
        self.run_links: dict[str, str] = {}

        self.body = tk.Frame(self, bg="#0d1117", padx=14, pady=12)
        self.body.pack(fill="both", expand=True)
        self.build_shell()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(400, lambda: self.attributes("-topmost", True))
        self.refresh()

    def place_on_screen(self) -> None:
        screen_w = max(self.winfo_screenwidth(), WINDOW_WIDTH + 40)
        screen_h = max(self.winfo_screenheight(), WINDOW_HEIGHT + 40)
        width = min(WINDOW_WIDTH, screen_w - 40)
        height = min(WINDOW_HEIGHT, screen_h - 80)
        x = max(10, int((screen_w - width) / 2))
        y = max(10, int((screen_h - height) / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def label(self, parent: tk.Widget, text: str, **kwargs: object) -> tk.Label:
        options = {
            "bg": "#0d1117",
            "fg": "#c9d1d9",
            "font": ("Segoe UI", 9),
            "anchor": "w",
            "justify": "left",
        }
        options.update(kwargs)
        return tk.Label(parent, text=text, **options)

    def section(self, text: str) -> None:
        self.label(self.body, text, fg="#58a6ff", font=("Segoe UI Semibold", 10)).pack(fill="x", pady=(12, 5))

    def build_shell(self) -> None:
        head = tk.Frame(self.body, bg="#0d1117")
        head.pack(fill="x")
        self.label(head, "SCRAPEADORACADEMICO", fg="#ffffff", font=("Segoe UI Semibold", 15)).pack(side="left")
        tk.Button(head, text="Actualizar", command=self.refresh, bg="#238636", fg="#ffffff", relief="flat").pack(side="right")

        self.status_var = tk.StringVar(value="Cargando...")
        self.label(self.body, "", textvariable=self.status_var, fg="#8b949e").pack(fill="x", pady=(3, 0))

        self.counts_var = tk.StringVar(value="")
        self.label(self.body, "", textvariable=self.counts_var, fg="#d8fff8", font=("Segoe UI Semibold", 9)).pack(fill="x", pady=(8, 0))

        self.section("Cascada")
        self.runs_frame = tk.Frame(self.body, bg="#0d1117")
        self.runs_frame.pack(fill="x")

        self.section("Ultimos 10 articulos")
        self.articles_frame = tk.Frame(self.body, bg="#0d1117")
        self.articles_frame.pack(fill="both", expand=True)

        self.section("Resumen STM")
        self.stm_frame = tk.Frame(self.body, bg="#0d1117")
        self.stm_frame.pack(fill="x")

        footer = tk.Frame(self.body, bg="#0d1117")
        footer.pack(fill="x", pady=(12, 0))
        tk.Button(footer, text="Dashboard", command=self.open_dashboard, bg="#1f6feb", fg="#ffffff", relief="flat").pack(side="left")
        tk.Button(footer, text="GitHub Actions", command=self.open_actions, bg="#30363d", fg="#ffffff", relief="flat").pack(side="left", padx=6)
        tk.Button(footer, text="Git pull", command=self.git_pull, bg="#30363d", fg="#ffffff", relief="flat").pack(side="right")

    def clear(self, frame: tk.Frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def refresh(self) -> None:
        try:
            counts = local_counts()
            self.counts_var.set(
                f"{counts['validados']} validados · {counts['revision']} en revision · {counts['rechazados']} rechazados"
            )
            runs = workflow_runs()
            self.render_runs(runs)
            self.render_articles(latest_articles())
            self.render_stm(stm_topics())
            self.status_var.set(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")
        self.after(REFRESH_MS, self.refresh)

    def render_runs(self, runs: list[dict[str, str]]) -> None:
        self.clear(self.runs_frame)
        self.run_links = {run["label"]: run.get("url", "") for run in runs}
        for run in runs:
            conclusion = run["conclusion"] or "en curso"
            color = "#3fb950" if conclusion == "success" else "#f85149" if conclusion == "failure" else "#d29922"
            row = tk.Frame(self.runs_frame, bg="#161b22", padx=8, pady=6)
            row.pack(fill="x", pady=2)
            self.label(row, run["label"], bg="#161b22", fg="#ffffff", font=("Segoe UI Semibold", 9), width=11).pack(side="left")
            self.label(row, f"{run['status']} · {conclusion}", bg="#161b22", fg=color).pack(side="left", fill="x", expand=True)
            self.label(row, run["updated_at"], bg="#161b22", fg="#8b949e").pack(side="right")

    def render_articles(self, articles: list[dict[str, str]]) -> None:
        self.clear(self.articles_frame)
        for article in articles:
            title = textwrap.shorten(article.get("title", "Sin titulo"), width=82, placeholder="...")
            meta = f"{article.get('first_seen_date', '-')} · {article.get('publication_year', '-')} · {article.get('source', '-')}"
            authors = textwrap.shorten(compact_authors(article.get("authors", "")), width=70, placeholder="...")
            block = tk.Frame(self.articles_frame, bg="#161b22", padx=8, pady=6)
            block.pack(fill="x", pady=2)
            self.label(block, title, bg="#161b22", fg="#ffffff", font=("Segoe UI Semibold", 8), wraplength=380).pack(fill="x")
            self.label(block, authors, bg="#161b22", fg="#8b949e", wraplength=380).pack(fill="x")
            self.label(block, meta, bg="#161b22", fg="#58a6ff").pack(fill="x")

    def render_stm(self, topics: list[dict[str, str]]) -> None:
        self.clear(self.stm_frame)
        if not topics:
            self.label(self.stm_frame, "Sin topicos STM disponibles.", fg="#8b949e").pack(fill="x")
            return
        for topic in topics:
            words = textwrap.shorten(topic.get("frex_top10", ""), width=64, placeholder="...")
            text = f"T{topic.get('topico', '-')} · {topic.get('prevalencia', '-')}% · {words}"
            self.label(self.stm_frame, text, fg="#c9d1d9", wraplength=390).pack(fill="x", pady=1)

    def open_dashboard(self) -> None:
        webbrowser.open(str(REPO_ROOT / "docs" / "index.html"))

    def open_actions(self) -> None:
        webbrowser.open(f"https://github.com/{OWNER}/{REPO}/actions")

    def git_pull(self) -> None:
        try:
            run_command(["git", "pull", "--ff-only"])
            self.refresh()
            messagebox.showinfo("SCRAPEADORACADEMICO", "Repositorio actualizado.")
        except Exception as exc:
            messagebox.showerror("SCRAPEADORACADEMICO", f"No se pudo actualizar:\n{exc}")


if __name__ == "__main__":
    Widget().mainloop()

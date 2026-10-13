#!/usr/bin/env python3
"""Publish generated corpus in a disposable Actions checkout, safely rebasing.

When concurrent updates conflict, regenerate from the latest catalog/Drive
instead of selecting one side of a CSV conflict or force-pushing old outputs.
"""
import os
import subprocess
from pathlib import Path


def run(*args, check=True):
    return subprocess.run(args, check=check)


def save():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("This publisher only runs in a disposable GitHub Actions checkout.")
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(1, 4):
        legacy = Path("data/corpus.csv")
        if legacy.exists():
            run("git", "rm", "--ignore-unmatch", "--cached", str(legacy))
            legacy.unlink()
        run("git", "add", "data/corpus.csv.gz", "data/extraction_log.csv", "data/drive_manifest.csv")
        if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
            print("Sin cambios en el corpus/manifiesto.", flush=True)
            return
        run("git", "commit", "-m", "Actualiza corpus y manifiesto de PDFs de Drive")
        run("git", "fetch", "origin", "main")
        rebased = run("git", "rebase", "origin/main", check=False).returncode == 0
        if rebased and run("git", "push", "origin", "HEAD:main", check=False).returncode == 0:
            return
        if not rebased:
            run("git", "rebase", "--abort")
        if attempt == 3:
            raise RuntimeError("No se pudo guardar el corpus tras tres intentos; no se sobrescribió main.")
        # Only this workflow's disposable checkout is reset. No force push.
        run("git", "fetch", "origin", "main")
        run("git", "reset", "--hard", "origin/main")
        print("Actualización concurrente: regenerando con la versión actual.", flush=True)
        run("Rscript", "extract_corpus.R")
        run("Rscript", "generate_drive_manifest.R")


if __name__ == "__main__":
    save()

import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/save_extracted_corpus.py"


def git(root, *args):
    return subprocess.run([shutil.which("git"), "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def setup_repos(tmp_path):
    remote, seed, worker, peer = [tmp_path / n for n in ("remote.git", "seed", "worker", "peer")]
    remote.mkdir(); git(remote, "init", "--bare")
    seed.mkdir(); git(seed, "init", "-b", "main")
    git(seed, "config", "user.name", "Test"); git(seed, "config", "user.email", "test@example.invalid")
    (seed / "data").mkdir()
    for f in ("corpus.csv.gz", "extraction_log.csv", "drive_manifest.csv"):
        (seed / "data" / f).write_text("base\n")
    (seed / "catalog.txt").write_text("base catalog\n")
    git(seed, "add", "."); git(seed, "commit", "-m", "base")
    git(seed, "remote", "add", "origin", str(remote)); git(seed, "push", "origin", "main")
    git(tmp_path, "clone", "--branch", "main", str(remote), str(worker))
    git(tmp_path, "clone", "--branch", "main", str(remote), str(peer))
    git(peer, "config", "user.name", "Peer"); git(peer, "config", "user.email", "peer@example.invalid")
    bindir = tmp_path / "bin"; bindir.mkdir()
    stub = bindir / "Rscript"
    stub.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n'
                    'fresh=Path("catalog.txt").read_text()\n'
                    'names=["corpus.csv.gz","extraction_log.csv"] if sys.argv[1]=="extract_corpus.R" else ["drive_manifest.csv"]\n'
                    'for name in names: Path("data",name).write_text("regenerated: "+fresh)\n')
    stub.chmod(0o755)
    env = {**os.environ, "GITHUB_ACTIONS": "true", "PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
    return remote, worker, peer, env


def update_peer(peer, conflict=False):
    (peer / "catalog.txt").write_text("latest catalog\n")
    if conflict:
        (peer / "data/drive_manifest.csv").write_text("concurrent manifest\n")
    git(peer, "add", "."); git(peer, "commit", "-m", "concurrent update"); git(peer, "push", "origin", "main")


def test_conflicting_manifest_is_regenerated_against_latest_catalog(tmp_path):
    remote, worker, peer, env = setup_repos(tmp_path)
    (worker / "data/drive_manifest.csv").write_text("stale worker manifest\n")
    (worker / "data/corpus.csv.gz").write_text("stale worker corpus\n")
    update_peer(peer, conflict=True)
    subprocess.run(["python3", str(SCRIPT)], cwd=worker, env=env, check=True, capture_output=True)
    assert git(remote, "show", "main:catalog.txt") == "latest catalog"
    for name in ("corpus.csv.gz", "extraction_log.csv", "drive_manifest.csv"):
        assert git(remote, "show", "main:data/" + name) == "regenerated: latest catalog"
    assert "concurrent update" in git(remote, "log", "--format=%s", "main")


def test_no_changes_does_not_add_commit(tmp_path):
    remote, worker, peer, env = setup_repos(tmp_path)
    before = git(remote, "rev-parse", "main")
    subprocess.run(["python3", str(SCRIPT)], cwd=worker, env=env, check=True, capture_output=True)
    assert git(remote, "rev-parse", "main") == before


def test_refuses_non_actions_checkout(tmp_path):
    env = {**os.environ, "GITHUB_ACTIONS": "false"}
    result = subprocess.run(["python3", str(SCRIPT)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "disposable GitHub Actions checkout" in result.stderr

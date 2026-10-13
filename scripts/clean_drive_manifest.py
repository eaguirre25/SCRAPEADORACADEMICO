"""Reconcile the checked-in manifest with verified duplicate moves."""
import csv
import json
import re
from pathlib import Path


def main():
    path = Path("data/drive_manifest.csv")
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = list(reader.fieldnames), list(reader)
    report = Path("data/drive_deduplication_report.json")
    removed = {r["id"] for r in json.loads(report.read_text()).get("moves", [])} if report.exists() else set()
    moves = json.loads(report.read_text()).get("moves", []) if report.exists() else []
    by_id = {r.get("drive_file_id"): r for r in rows}
    for move in moves:
        original = by_id.get(move["id"], {})
        kept = by_id.get(move["kept_id"])
        doi = original.get("doi", "")
        # An old DOI filename can identify a verified identical copy under a new name.
        if not re.match(r"^10\.\d{4,9}/", doi):
            doi = re.sub(r"\.pdf$", "", move.get("name", ""), flags=re.I).replace("_", "/", 1)
        if kept is not None and re.match(r"^10\.\d{4,9}/", doi) and not re.match(r"^10\.\d{4,9}/", kept.get("doi", "")):
            kept["doi"] = doi.lower()
    active = [r for r in rows if r.get("drive_file_id") not in removed]
    for row in active:
        if not re.match(r"^10\.\d{4,9}/", row.get("doi", "")):
            row["doi"] = ""
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(active)
    temporary.replace(path)
    print(f"Manifiesto Drive: {len(active)} PDF activos")


if __name__ == "__main__":
    main()

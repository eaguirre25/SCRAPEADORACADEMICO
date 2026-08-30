#!/usr/bin/env python3
"""Actualiza docs/report_history.json recalculando todas las corridas históricas desde master_records.csv."""
import csv, json
from collections import defaultdict
from pathlib import Path

MASTER = Path('data/master_records.csv')
REPORT_FILE = Path('docs/report_history.json')

if not MASTER.exists():
    raise SystemExit('Falta data/master_records.csv')

csv.field_size_limit(150_000_000)

runs = defaultdict(list)
with MASTER.open(encoding='utf-8-sig', newline='', errors='replace') as f:
    for r in csv.DictReader(f):
        fsd = (r.get('first_seen_date') or '').strip()
        if fsd and fsd >= '2026-07-01':
            runs[fsd].append(r)

sorted_dates = sorted(runs.keys())
cumulative = 1814 - sum(len(runs[d]) for d in sorted_dates) # Base acumulada limpia tras deduplicación

report_history = []
current_base = 1550 # Base inicial antes de julio

for d in sorted_dates:
    items = runs[d]
    new_count = len(items)
    current_base += new_count
    
    # Conteo de fuentes
    src_counts = defaultdict(int)
    for it in items:
        s = it.get('source') or it.get('origin') or 'OpenAlex'
        src_counts[s] += 1
    
    src_str = ' · '.join(f'{k}: {v}' for k, v in src_counts.items()) if src_counts else 'OpenAlex'
    
    report_history.append({
        'date': d,
        'base': current_base,
        'new': new_count,
        'sources': src_str
    })

REPORT_FILE.write_text(json.dumps(report_history, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Actualizado docs/report_history.json con {len(report_history)} informes hasta {sorted_dates[-1]}!')

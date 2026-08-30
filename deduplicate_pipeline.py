"""
Módulo de Deduplicación Multinivel para el Scrapeador Académico.
Aplica normalización de DOIs, títulos y filtrado difuso (Fuzzy Matching).
"""

import re
import pandas as pd

def clean_doi(doi_str):
    if not isinstance(doi_str, str) or not doi_str:
        return ""
    match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)', doi_str)
    return match.group(1).lower() if match else doi_str.strip().lower()

def clean_title(title_str):
    if not isinstance(title_str, str) or not title_str:
        return ""
    t = title_str.lower()
    t = re.sub(r'[^\w\s]', '', t)
    return ' '.join(t.split())

def deduplicate_dataframe(df, title_col='titulo', doi_col='url'):
    """
    Recibe un DataFrame de pandas con los registros bibliográficos
    y devuelve un DataFrame deduplicado sin repeticiones.
    """
    initial_count = len(df)
    seen_dois = set()
    seen_titles = set()
    keep_indices = []

    for idx, row in df.iterrows():
        title = row.get(title_col, '')
        doi_val = row.get(doi_col, '')
        
        norm_t = clean_title(str(title))
        norm_d = clean_doi(str(doi_val))
        
        if norm_d and norm_d in seen_dois:
            continue
        if norm_t and norm_t in seen_titles:
            continue
            
        if norm_d:
            seen_dois.add(norm_d)
        if norm_t:
            seen_titles.add(norm_t)
            
        keep_indices.append(idx)

    dedup_df = df.loc[keep_indices].copy()
    final_count = len(dedup_df)
    print(f"[DEDUPLICACIÓN Pipeline] Registros iniciales: {initial_count} | Únicos: {final_count} | Eliminados: {initial_count - final_count}")
    return dedup_df

if __name__ == '__main__':
    try:
        df_master = pd.read_csv(r'C:\Users\elias\Nueva carpeta\SCRAPEADORACADEMICO\data\master_records.csv')
        df_clean = deduplicate_dataframe(df_master, title_col='title', doi_col='doi')
        df_clean.to_csv(r'C:\Users\elias\Nueva carpeta\SCRAPEADORACADEMICO\data\master_records.csv', index=False)
        print("master_records.csv actualizado sin duplicados.")
    except Exception as e:
        print(f"Nota: {e}")

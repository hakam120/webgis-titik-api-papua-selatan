#!/usr/bin/env python3
"""Klimatologi bulanan 2015-2025 per titik iklim dan untuk provinsi (sekali jalan, lokal) -> data/prakiraan/dasar_iklim.json.
Masukan: iklim_bulanan_titik.csv hasil bangun_riwayat_iklim.py."""
import argparse, csv, json, os
import enso_lib as E
from perbarui_prakiraan import TITIK_MUSIM

ap = argparse.ArgumentParser(); ap.add_argument('--csv', required=True)
ap.add_argument('--data', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'prakiraan'))
a = ap.parse_args()
v = {}   # (id, tahun, bulan) -> (hujan, fwi, dc)
for r in csv.DictReader(open(a.csv, encoding='utf-8')):
    y, m = int(r['bulan'][:4]), int(r['bulan'][5:7])
    if 2015 <= y <= 2025:
        v[(int(r['id']), y, m)] = (float(r['hujan_mm']), float(r['fwi']), float(r['dc']))
ids = sorted(set(k[0] for k in v)); th = list(range(2015, 2026))
rata = lambda x: sum(x) / len(x)
titik = {str(p): {'hujan': [round(rata([v[(p, y, m)][0] for y in th]), 1) for m in range(1, 13)],
                  'fwi': [round(rata([v[(p, y, m)][1] for y in th]), 2) for m in range(1, 13)],
                  'dc': [round(rata([v[(p, y, m)][2] for y in th]), 1) for m in range(1, 13)]} for p in ids}
prov = {'hujan': [], 'hujan_t33': [], 'hujan_t67': [], 'fwi': [], 'fwi_t33': [], 'fwi_t67': []}
for m in range(1, 13):
    hp = [rata([v[(p, y, m)][0] for p in TITIK_MUSIM]) for y in th]; fp = [rata([v[(p, y, m)][1] for p in TITIK_MUSIM]) for y in th]
    prov['hujan'].append(round(rata(hp), 1)); prov['hujan_t33'].append(round(E.kuantil(hp, 1 / 3), 1)); prov['hujan_t67'].append(round(E.kuantil(hp, 2 / 3), 1))
    prov['fwi'].append(round(rata(fp), 2)); prov['fwi_t33'].append(round(E.kuantil(fp, 1 / 3), 2)); prov['fwi_t67'].append(round(E.kuantil(fp, 2 / 3), 2))
json.dump({'periode': '2015-2025', 'sumber': 'Arsip ERA5/ERA5-Land Open-Meteo; FWI dihitung sendiri (Van Wagner 1987)', 'titik': titik, 'provinsi': prov},
          open(os.path.join(a.data, 'dasar_iklim.json'), 'w', encoding='utf-8'), separators=(',', ':'))
print('provinsi hujan normal per bulan:', prov['hujan']); print('provinsi FWI normal per bulan:', prov['fwi'])

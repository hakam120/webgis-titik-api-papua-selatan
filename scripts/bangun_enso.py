#!/usr/bin/env python3
"""Hubungan ENSO/IOD - titik api MODIS Agu-Nov Papua Selatan 2001-2025 (sekali jalan, lokal).

Masukan: arsip tahunan FIRMS MODIS per negara 2001-2014 (--modis), tabel titik api Tanah Papua 2015-2025 (--papua),
FIRMS 2026 (--f2026, opsional). Keluaran: data/prakiraan/enso_model.json (dipakai pembaru otomatis dan WebGIS).
"""
import argparse, csv, glob, gzip, json, os, datetime as dt
import enso_lib as E

ap = argparse.ArgumentParser()
ap.add_argument('--modis', required=True); ap.add_argument('--papua', required=True); ap.add_argument('--f2026', default='')
ap.add_argument('--data', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data'))
a = ap.parse_args()
meta = json.load(open(os.path.join(a.data, 'acuan_meta.json'), encoding='utf-8'))
grid = gzip.open(os.path.join(a.data, 'acuan_0005.bin.gz'), 'rb').read()
nb, nx, ny, lon0, lat1, dx = len(meta['band']), meta['nx'], meta['ny'], meta['lon0'], meta['lat1'], meta['dx']


def di_provinsi(lon, lat):
    c, r = int((lon - lon0) / dx), int((lat1 - lat) / dx)
    return 0 <= c < nx and 0 <= r < ny and grid[(r * nx + c) * nb] > 0


bulanan = {}   # (tahun, bulan) -> jumlah deteksi MODIS kebakaran vegetasi
for f in sorted(glob.glob(os.path.join(a.modis, 'modis_*.csv'))):
    for r in csv.DictReader(open(f, encoding='utf-8')):
        la, lo = float(r['latitude']), float(r['longitude'])
        if not (-9.4 <= la <= -4.0 and 137.1 <= lo <= 141.2) or r.get('type', '0') != '0' or not di_provinsi(lo, la):
            continue
        k = (int(r['acq_date'][:4]), int(r['acq_date'][5:7])); bulanan[k] = bulanan.get(k, 0) + 1
for r in csv.DictReader(open(a.papua, encoding='utf-8-sig')):
    if r['sensor'] == 'MODIS' and r['province'].strip('"') == 'Papua Selatan' and r['type'] == '0':
        k = (int(r['year']), int(r['month'])); bulanan[k] = bulanan.get(k, 0) + 1
n2026 = None
if a.f2026 and os.path.exists(a.f2026):
    n2026 = 0
    for r in csv.DictReader(open(a.f2026, encoding='utf-8-sig')):
        la, lo = float(r['latitude']), float(r['longitude'])
        if r['acq_date'][5:7] in ('08', '09', '10', '11') and di_provinsi(lo, la):
            n2026 += 1

oni = E.baca_oni(E.unduh_teks(E.URL_ONI))
dmi = {}
try:
    for l in E.unduh_teks('https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data').splitlines():
        p = l.split()
        if len(p) == 13 and p[0].isdigit():
            v = [float(x) for x in p[8:11]]   # Agu, Sep, Okt
            if all(x > -90 for x in v):
                dmi[int(p[0])] = sum(v) / 3
except Exception as e:
    print('DMI tidak tersedia:', e)

tahun = list(range(2001, 2026))
n = [sum(bulanan.get((y, m), 0) for m in (8, 9, 10, 11)) for y in tahun]
y = [__import__('math').log10(v + 1) for v in n]
x1 = [oni[(t, 'ASO')] for t in tahun]
b1, r2_1, sd1 = E.ols([x1], y)
# uji sisih-satu-tahun
pred = []
for i in range(len(tahun)):
    bb, _, _ = E.ols([[v for j, v in enumerate(x1) if j != i]], [v for j, v in enumerate(y) if j != i]); pred.append(bb[0] + bb[1] * x1[i])
r_loo = E.korelasi(pred, y)
hasil = {
    'sumber': 'Titik api MODIS C6.1 (NASA FIRMS, kebakaran vegetasi) Agu-Nov di Provinsi Papua Selatan; ONI NOAA CPC (ERSSTv5, Nino 3.4); DMI NOAA PSL (HadISST)',
    'tahun': tahun, 'titik_agu_nov': n, 'oni_aso': x1, 'dmi_aso': [round(dmi[t], 2) if t in dmi else None for t in tahun],
    'koef_oni': [round(v, 4) for v in b1], 'r2_oni': round(r2_1, 3), 'sisa_sd_oni': round(sd1, 3), 'r_sisih_satu_tahun': round(r_loo, 3),
    'tercile': [round(E.kuantil(n, 1 / 3)), round(E.kuantil(n, 2 / 3))], 'median': round(E.kuantil(n, 0.5)), 'titik_2026_agu_nov': n2026,
    'bulanan_rata2': [round(sum(bulanan.get((t, m), 0) for t in tahun) / len(tahun), 1) for m in range(1, 13)],
}
if all(t in dmi for t in tahun):
    x2 = [dmi[t] for t in tahun]; b2, r2_2, sd2 = E.ols([x1, x2], y)
    hasil.update({'koef_oni_dmi': [round(v, 4) for v in b2], 'r2_oni_dmi': round(r2_2, 3), 'sisa_sd_oni_dmi': round(sd2, 3), 'r_oni_dmi': round(E.korelasi(x1, x2), 2)})
hasil['prospek'] = E.prospek_analog(oni, b1, sd1, hasil['tercile'], dt.date.today())
os.makedirs(os.path.join(a.data, 'prakiraan'), exist_ok=True)
json.dump(hasil, open(os.path.join(a.data, 'prakiraan', 'enso_model.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('tahun', tahun[0], '-', tahun[-1]); print('titik Agu-Nov', n); print('ONI ASO', x1)
print({k: hasil[k] for k in hasil if k.startswith(('koef', 'r2', 'r_', 'sisa', 'tercile', 'median', 'titik_2026'))}); print(hasil['prospek'])

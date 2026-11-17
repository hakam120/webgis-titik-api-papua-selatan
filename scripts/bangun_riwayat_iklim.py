#!/usr/bin/env python3
"""Membangun riwayat iklim harian 2015-kini di titik iklim (sekali jalan, di komputer lokal).

Keluaran (folder --keluar, bahan pelatihan model dinamis dan kalibrasi FWI):
  arsip/titik_NN.json        data mentah Open-Meteo (dipakai ulang bila sudah ada)
  harian_fwi.csv             FWI harian per titik
  iklim_bulanan_titik.csv    hujan, FWI, DC, suhu, kelembapan bulanan per titik
Keluaran ke repositori (--data): prakiraan/harian_terkini.json = 400 hari terakhir + keadaan FWI (benih pembaru otomatis).
"""
import argparse, json, os, time, datetime as dt
from collections import OrderedDict
import prakiraan_lib as L

ap = argparse.ArgumentParser()
ap.add_argument('--keluar', required=True)
ap.add_argument('--data', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'prakiraan'))
ap.add_argument('--awal', default='2015-01-01')
ap.add_argument('--akhir', default=(dt.date.today() - dt.timedelta(days=6)).isoformat())
ap.add_argument('--jeda', type=float, default=15.0)
a = ap.parse_args()
os.makedirs(os.path.join(a.keluar, 'arsip'), exist_ok=True); os.makedirs(a.data, exist_ok=True)

harian = OrderedDict(); bulanan = []; terkini = {'titik': [list(t) for t in L.TITIK], 'tanggal': None, 'keadaan': {}, 'hari': None, 'nilai': {}}
for pid, lon, lat in L.TITIK:
    f = os.path.join(a.keluar, 'arsip', 'titik_%02d.json' % pid)
    d = None
    if os.path.exists(f):
        d = json.load(open(f, encoding='utf-8'))
        if d.get('daily', {}).get('time', [''])[-1] < a.akhir:
            d = None
    if d is None:
        d = L.ambil_json(L.url_arsip(lon, lat, a.awal, a.akhir))
        json.dump(d, open(f, 'w', encoding='utf-8'))
        print('unduh titik %02d (%.2f, %.2f): %d hari' % (pid, lon, lat, len(d['daily']['time'])), flush=True)
        time.sleep(a.jeda)
    deret = L.deret_harian(d['daily'])
    hasil, keadaan = L.jalankan_fwi(deret, L.AWAL_FWI)
    agg = OrderedDict()
    for tg, fwi, dc, hujan, tm, rm in hasil:
        harian.setdefault(tg, {})[pid] = fwi
        g = agg.setdefault(tg[:7], [0.0, 0.0, 0.0, 0.0, 0.0, 0])
        g[0] += hujan; g[1] += fwi; g[2] += dc; g[3] += tm; g[4] += rm; g[5] += 1
    for ym, g in agg.items():
        n = g[5]
        bulanan.append((pid, lon, lat, ym, round(g[0], 1), round(g[1] / n, 2), round(g[2] / n, 1), round(g[3] / n, 2), round(g[4] / n, 1), n))
    ekor = hasil[-400:]
    terkini['tanggal'] = ekor[-1][0]; terkini['hari'] = [h[0] for h in ekor]
    terkini['keadaan'][str(pid)] = [round(x, 3) for x in keadaan]
    terkini['nilai'][str(pid)] = {'fwi': [round(h[1], 1) for h in ekor], 'dc': [round(h[2]) for h in ekor], 'hujan': [round(h[3], 1) for h in ekor],
                                  'suhu': [round(h[4], 1) for h in ekor], 'rh': [round(h[5]) for h in ekor]}

ids = [t[0] for t in L.TITIK]
with open(os.path.join(a.keluar, 'harian_fwi.csv'), 'w', encoding='utf-8') as w:
    w.write('tanggal,' + ','.join('p%d' % i for i in ids) + '\n')
    for tg, v in harian.items():
        w.write(tg + ',' + ','.join('%.1f' % v[i] if i in v else '' for i in ids) + '\n')
with open(os.path.join(a.keluar, 'iklim_bulanan_titik.csv'), 'w', encoding='utf-8') as w:
    w.write('id,lon,lat,bulan,hujan_mm,fwi,dc,suhu_c,rh_persen,hari\n')
    for r in bulanan:
        w.write(','.join(str(x) for x in r) + '\n')
json.dump(terkini, open(os.path.join(a.data, 'harian_terkini.json'), 'w', encoding='utf-8'), separators=(',', ':'))
print('selesai: %d titik, %d hari, s.d. %s' % (len(ids), len(harian), terkini['tanggal']))

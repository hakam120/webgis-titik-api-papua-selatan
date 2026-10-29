#!/usr/bin/env python3
"""Perbarui data titik api 7 hari terakhir WebGIS Papua Selatan dari NASA FIRMS NRT (tanpa MAP_KEY).

Dijalankan oleh GitHub Actions (.github/workflows/perbarui-dan-terbitkan.yml) setiap 6 jam.
Atribut tiap titik (kabupaten, kecamatan, kelas bahaya model, gambut, fungsi kawasan, konsesi,
rawan KLHK) diambil dari grid acuan 0,005 derajat (data/acuan_0005.bin.gz) yang dibuat oleh
skrip 09_webgis_v2.ps1 dari raster 100 m. Hanya pustaka standar Python yang dipakai.
"""
import csv, datetime, gzip, io, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
UA = 'PjBL-SIG-K05-Kelompok3-WebGIS/1.0'
SUMBER = [  # (berkas FIRMS, kode sensor)
    ('suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_SouthEast_Asia_7d.csv', None),
    ('noaa-20-viirs-c2/csv/J1_VIIRS_C2_SouthEast_Asia_7d.csv', None),
    ('noaa-21-viirs-c2/csv/J2_VIIRS_C2_SouthEast_Asia_7d.csv', None),
    ('modis-c6.1/csv/MODIS_C6_1_SouthEast_Asia_7d.csv', None),
]
SAT = {'N': 'S', 'N20': 'N20', 'N21': 'N21', 'T': 'MT', 'A': 'MA'}
NAMA_SENSOR = {'S': 'VIIRS_SNPP', 'N20': 'VIIRS_NOAA20', 'N21': 'VIIRS_NOAA21', 'MT': 'MODIS_Terra', 'MA': 'MODIS_Aqua'}


def unduh(path):
    url = 'https://firms.modaps.eosdis.nasa.gov/data/active_fire/' + path
    for coba in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read().decode('utf-8')
        except Exception as e:  # noqa: BLE001
            print('gagal', url, e, file=sys.stderr)
    return None


def main():
    meta = json.load(open(os.path.join(DATA, 'acuan_meta.json'), encoding='utf-8'))
    with gzip.open(os.path.join(DATA, 'acuan_0005.bin.gz'), 'rb') as f:
        grid = f.read()
    nb, nx, ny = len(meta['band']), meta['nx'], meta['ny']
    lon0, lat1, dx = meta['lon0'], meta['lat1'], meta['dx']
    band = {b: i for i, b in enumerate(meta['band'])}

    def acuan(lon, lat):
        c, r = int((lon - lon0) / dx), int((lat1 - lat) / dx)
        if c < 0 or r < 0 or c >= nx or r >= ny:
            return None
        o = (r * nx + c) * nb
        return grid[o:o + nb]

    titik, seen = [], set()
    for path, _ in SUMBER:
        teks = unduh(path)
        if teks is None:
            print('sumber tidak tersedia, data lama dipertahankan:', path)
            return 0
        for r in csv.DictReader(io.StringIO(teks)):
            la, lo = float(r['latitude']), float(r['longitude'])
            if not (-9.4 <= la <= -4.0 and 137.1 <= lo <= 141.2):
                continue
            v = acuan(lo, la)
            if v is None or v[band['kab']] == 0:
                continue
            s = SAT.get(r['satellite'], r['satellite'])
            t = r['acq_time'].zfill(4)
            key = '%s|%s|%s|%.4f|%.4f' % (s, r['acq_date'], t, la, lo)
            if key in seen:
                continue
            seen.add(key)
            c = r['confidence'].lower()
            c = {'low': 'l', 'nominal': 'n', 'high': 'h'}.get(c, c)
            titik.append({'lon': lo, 'lat': la, 's': s, 'd': r['acq_date'], 't': t, 'c': c, 'f': float(r['frp']),
                          'k': v[band['kab']], 'kc': v[band['kec']], 'z': v[band['kelas']], 'g': v[band['gambut_feg']],
                          'gm': v[band['gambut_ml']], 'kh': v[band['kawasan']], 'ks': v[band['konsesi']], 'rk': v[band['rawan']]})
    if not titik:
        print('tidak ada titik; data lama dipertahankan')
        return 0
    titik.sort(key=lambda p: (p['d'], p['t']))
    akhir = titik[-1]
    d_akhir = datetime.date.fromisoformat(akhir['d'])
    d_awal = (d_akhir - datetime.timedelta(days=6)).isoformat()
    titik = [p for p in titik if p['d'] >= d_awal]
    tulis(meta, titik, akhir, d_awal)
    return 0


def hitung(daftar, kunci, label=None):
    h = {}
    for p in daftar:
        k = kunci(p)
        if label is not None:
            k = label[k] if isinstance(label, list) and k < len(label) else (label.get(str(k), 'Lainnya') if isinstance(label, dict) else k)
        h[k] = h.get(k, 0) + 1
    return dict(sorted(h.items(), key=lambda kv: -kv[1]))


def tulis(meta, titik, akhir, d_awal):
    kab, kec = meta['kabupaten'], meta['kecamatan']
    t_utc = datetime.datetime.strptime(akhir['d'] + akhir['t'], '%Y-%m-%d%H%M')
    ring = {
        'dibuat_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M'),
        'data_terakhir_utc': t_utc.strftime('%Y-%m-%d %H:%M'),
        'data_terakhir_wit': (t_utc + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M'),
        'awal': d_awal, 'akhir': akhir['d'], 'jumlah': len(titik),
        'frp_total_MW': round(sum(p['f'] for p in titik)),
        'per_sensor': hitung(titik, lambda p: NAMA_SENSOR.get(p['s'], p['s'])),
        'per_kabupaten': hitung(titik, lambda p: p['k'], kab),
        'kecamatan_teratas': [[kec[k] if k < len(kec) else '?', n] for k, n in list(hitung(titik, lambda p: p['kc']).items())[:10] if k],
        'per_kelas_bahaya': {str(z): sum(1 for p in titik if p['z'] == z) for z in range(0, 6)},
        'gambut_peatml_50': sum(1 for p in titik if p['gm'] >= 50),
        'gambut_feg': sum(1 for p in titik if p['g'] > 0),
        'fungsi_kawasan': hitung(titik, lambda p: p['kh'], meta['kawasan']),
        'konsesi': hitung(titik, lambda p: p['ks'], meta['konsesi']),
        'rawan_klhk': hitung(titik, lambda p: p['rk'], meta['rawan']),
        'harian': {},
    }
    for p in titik:
        h = ring['harian'].setdefault(p['d'], {})
        n = NAMA_SENSOR.get(p['s'], p['s'])
        h[n] = h.get(n, 0) + 1
    ring['harian'] = dict(sorted(ring['harian'].items()))
    fitur = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(p['lon'], 4), round(p['lat'], 4)]},
              'properties': {k: p[k] for k in ('s', 'd', 't', 'c', 'f', 'k', 'kc', 'z', 'g', 'gm', 'kh', 'ks', 'rk')}} for p in titik]
    gj = {'type': 'FeatureCollection', 'features': fitur}
    with open(os.path.join(DATA, 'titik_api_7hari.js'), 'w', encoding='utf-8') as f:
        f.write('window.TITIK7 = ' + json.dumps(gj, separators=(',', ':'), ensure_ascii=False) + ';\n')
        f.write('window.TERKINI = ' + json.dumps(ring, ensure_ascii=False) + ';\n')
    # arsip harian (bertambah terus): jumlah titik per tanggal per kabupaten (semua sensor)
    ap = os.path.join(DATA, 'arsip_harian.js')
    arsip = {}
    if os.path.exists(ap):
        teks = open(ap, encoding='utf-8').read()
        arsip = json.loads(teks[teks.index('=') + 1:].strip().rstrip(';'))
    for d in sorted({p['d'] for p in titik}):
        hari = [p for p in titik if p['d'] == d]
        arsip[d] = {'total': len(hari), **{kab[i]: sum(1 for p in hari if p['k'] == i) for i in range(1, len(kab))}}
    with open(ap, 'w', encoding='utf-8') as f:
        f.write('window.ARSIP = ' + json.dumps(dict(sorted(arsip.items())), ensure_ascii=False) + ';\n')
    print('titik 7 hari:', len(titik), '| terakhir', ring['data_terakhir_wit'], 'WIT')


if __name__ == '__main__':
    sys.exit(main())

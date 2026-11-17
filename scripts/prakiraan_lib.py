#!/usr/bin/env python3
"""Pustaka prakiraan WebGIS Titik Api Papua Selatan.

Sumber data tanpa kunci akun (Open-Meteo, CC BY 4.0):
  - arsip cuaca harian ERA5/ERA5-Land  : archive-api.open-meteo.com
  - prakiraan cuaca 16 hari            : api.open-meteo.com
  - prakiraan musiman ensemble 51 anggota (±7 bulan): seasonal-api.open-meteo.com
Fire Weather Index (FWI) Kanada dihitung sendiri dari data harian dengan definisi yang sama untuk ketiga sumber:
  suhu = suhu maksimum harian, kelembapan = kelembapan minimum harian,
  angin = rata-rata (kecepatan rata-rata, kecepatan maksimum) 10 m, hujan = jumlah harian.
"""
import json, math, time, urllib.request, urllib.error

# titik iklim (kisi ±0,75 derajat di daratan Provinsi Papua Selatan): id, bujur, lintang
TITIK = [
    (1, 137.75, -8.25), (2, 138.50, -8.25), (3, 139.25, -8.00), (4, 140.00, -8.05), (5, 140.75, -8.25),
    (6, 138.50, -7.50), (7, 139.25, -7.50), (8, 140.00, -7.50), (9, 140.75, -7.50),
    (10, 138.75, -6.75), (11, 139.25, -6.75), (12, 140.00, -6.75), (13, 140.75, -6.75),
    (14, 138.50, -6.00), (15, 139.25, -6.00), (16, 140.00, -6.00), (17, 140.75, -6.00),
    (18, 137.75, -5.25), (19, 138.50, -5.25), (20, 139.25, -5.25), (21, 140.00, -5.25), (22, 140.60, -5.45),
    (23, 140.85, -8.85),
]
VAR_HARIAN = ['temperature_2m_max', 'temperature_2m_mean', 'relative_humidity_2m_mean', 'relative_humidity_2m_min',
              'wind_speed_10m_max', 'wind_speed_10m_mean', 'precipitation_sum']
ZONA = 'Asia%2FJayapura'
UA = {'User-Agent': 'webgis-titik-api-papua-selatan/1.0 (proyek akademik PjBL SIG ITB)'}
AWAL_FWI = (85.0, 6.0, 15.0)   # FFMC, DMC, DC awal (nilai baku Van Wagner 1987)


def ambil_json(url, coba=6, jeda=20, batas_waktu=120):
    """GET JSON dengan percobaan ulang; 429 (batas laju) ditunggu lebih lama."""
    err = None
    for k in range(coba):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=batas_waktu) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err = e
            time.sleep(jeda * (k + 1) * (3 if e.code == 429 else 1))
        except Exception as e:   # jaringan
            err = e
            time.sleep(jeda * (k + 1))
    raise RuntimeError('gagal mengambil %s: %s' % (url.split('?')[0], err))


def url_arsip(lon, lat, awal, akhir):
    return ('https://archive-api.open-meteo.com/v1/archive?latitude=%.4f&longitude=%.4f&start_date=%s&end_date=%s&daily=%s&timezone=%s'
            % (lat, lon, awal, akhir, ','.join(VAR_HARIAN), ZONA))


def url_prakiraan(lon, lat, hari_lalu=10, hari_depan=16):
    return ('https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&past_days=%d&forecast_days=%d&daily=%s&timezone=%s'
            % (lat, lon, hari_lalu, hari_depan, ','.join(VAR_HARIAN), ZONA))


def url_musiman(lon, lat, hari=215):
    return ('https://seasonal-api.open-meteo.com/v1/seasonal?latitude=%.4f&longitude=%.4f&forecast_days=%d&daily=%s&timezone=%s'
            % (lat, lon, hari, ','.join(VAR_HARIAN), ZONA))


# ---------- Fire Weather Index Kanada (Van Wagner 1987; Wang dkk. 2015), lintang ekuator: Le = 9, Lf = 1,4 ----------
def fwi_langkah(keadaan, t, rh, ws, hujan):
    """Satu hari. keadaan = (FFMC, DMC, DC) kemarin. Mengembalikan (FFMC, DMC, DC, ISI, BUI, FWI)."""
    f0, p0, d0 = keadaan
    rh = min(max(rh, 0.0), 100.0); ws = max(ws, 0.0); hujan = max(hujan, 0.0)
    # FFMC
    mo = 147.2 * (101.0 - f0) / (59.5 + f0)
    if hujan > 0.5:
        rf = hujan - 0.5
        mr = mo + 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))
        if mo > 150.0:
            mr += 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rf)
        mo = min(mr, 250.0)
    ed = 0.942 * rh ** 0.679 + 11.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * rh))
    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(ws) * (1.0 - (rh / 100.0) ** 8)
        m = ed + (mo - ed) * 10.0 ** (-ko * 0.581 * math.exp(0.0365 * t))
    else:
        ew = 0.618 * rh ** 0.753 + 10.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * rh))
        if mo < ew:
            k1 = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * math.sqrt(ws) * (1.0 - ((100.0 - rh) / 100.0) ** 8)
            m = ew - (ew - mo) * 10.0 ** (-k1 * 0.581 * math.exp(0.0365 * t))
        else:
            m = mo
    ffmc = min(max(59.5 * (250.0 - m) / (147.2 + m), 0.0), 101.0)
    # DMC
    if hujan > 1.5:
        re = 0.92 * hujan - 1.27
        mo2 = 20.0 + math.exp(5.6348 - p0 / 43.43)
        b = 100.0 / (0.5 + 0.3 * p0) if p0 <= 33.0 else (14.0 - 1.3 * math.log(p0) if p0 <= 65.0 else 6.2 * math.log(p0) - 17.2)
        mr2 = mo2 + 1000.0 * re / (48.77 + b * re)
        pr = max(244.72 - 43.43 * math.log(mr2 - 20.0), 0.0)
    else:
        pr = p0
    dmc = pr + (100.0 * 1.894 * (t + 1.1) * (100.0 - rh) * 9.0 * 1e-6 if t > -1.1 else 0.0)
    # DC
    if hujan > 2.8:
        rd = 0.83 * hujan - 1.27
        qr = 800.0 * math.exp(-d0 / 400.0) + 3.937 * rd
        dr = max(400.0 * math.log(800.0 / qr), 0.0)
    else:
        dr = d0
    dc = dr + 0.5 * max((0.36 * (t + 2.8) + 1.4) if t > -2.8 else 1.4, 0.0)
    # ISI, BUI, FWI
    mm = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    isi = 0.208 * math.exp(0.05039 * ws) * 91.9 * math.exp(-0.1386 * mm) * (1.0 + mm ** 5.31 / 4.93e7)
    if dmc <= 0.4 * dc:
        bui = 0.8 * dmc * dc / (dmc + 0.4 * dc) if (dmc + 0.4 * dc) > 0 else 0.0
    else:
        bui = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    bui = max(bui, 0.0)
    fd = 0.626 * bui ** 0.809 + 2.0 if bui <= 80.0 else 1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui))
    bb = 0.1 * isi * fd
    fwi = math.exp(2.72 * (0.434 * math.log(bb)) ** 0.647) if bb > 1.0 else bb
    return ffmc, dmc, dc, isi, bui, fwi


def deret_harian(d, akhiran=''):
    """Susun daftar (tanggal, tmax, tmean, rhmean, rhmin, angin, hujan) dari blok 'daily' Open-Meteo; hari tanpa data dilewati.
    akhiran: '' atau '_memberNN' untuk anggota ensemble musiman."""
    out = []
    g = lambda k: d.get(k + akhiran)
    tx, tm, rm, rn, wx, wm, pr = (g(v) for v in VAR_HARIAN)
    if tx is None or rn is None or pr is None:
        return out
    for i, tg in enumerate(d['time']):
        v = (tx[i], rn[i], pr[i])
        if any(x is None for x in v):
            continue
        w1 = wm[i] if wm and wm[i] is not None else None
        w2 = wx[i] if wx and wx[i] is not None else None
        angin = (w1 + w2) / 2.0 if w1 is not None and w2 is not None else (w2 * 0.7 if w2 is not None else (w1 * 1.4 if w1 is not None else 8.0))
        out.append((tg, tx[i], tm[i] if tm and tm[i] is not None else tx[i] - 4.0, rm[i] if rm and rm[i] is not None else rn[i] + 15.0, rn[i], angin, pr[i]))
    return out


def jalankan_fwi(deret, keadaan):
    """deret dari deret_harian; mengembalikan (daftar (tanggal, fwi, dc, hujan, tmean, rhmean), keadaan akhir)."""
    hasil = []
    for tg, tx, tm, rm, rn, angin, hujan in deret:
        f, p, dcv, isi, bui, fwi = fwi_langkah(keadaan, tx, rn, angin, hujan)
        keadaan = (f, p, dcv)
        hasil.append((tg, fwi, dcv, hujan, tm, rm))
    return hasil, keadaan

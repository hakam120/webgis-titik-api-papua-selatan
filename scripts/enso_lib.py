#!/usr/bin/env python3
"""Hubungan ENSO - titik api musim kebakaran (Agu-Nov) Papua Selatan dan prospek berbasis analog. Pustaka standar saja."""
import math, urllib.request

URL_ONI = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
MUSIM = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']
UA = {'User-Agent': 'webgis-titik-api-papua-selatan/1.0 (proyek akademik PjBL SIG ITB)'}


def unduh_teks(url, batas=90):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=batas) as r:
        return r.read().decode('utf-8', 'replace')


def baca_oni(teks):
    """{(tahun, 'ASO'): anomali} dari oni.ascii.txt NOAA CPC."""
    o = {}
    for l in teks.splitlines():
        p = l.split()
        if len(p) == 4 and p[0] in MUSIM:
            try:
                o[(int(p[1]), p[0])] = float(p[3])
            except ValueError:
                pass
    return o


def ols(xs, y):
    """Regresi linear kuadrat terkecil; xs = daftar kolom prediktor. Mengembalikan (koef [intersep, b1, ...], r2, simpangan sisa)."""
    n, k = len(y), len(xs) + 1
    X = [[1.0] + [c[i] for c in xs] for i in range(n)]
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] + [sum(X[i][a] * y[i] for i in range(n))] for a in range(k)]
    for a in range(k):   # eliminasi Gauss dengan pivot
        p = max(range(a, k), key=lambda r: abs(A[r][a])); A[a], A[p] = A[p], A[a]
        for r in range(k):
            if r != a:
                f = A[r][a] / A[a][a]
                A[r] = [A[r][c] - f * A[a][c] for c in range(k + 1)]
    b = [A[a][k] / A[a][a] for a in range(k)]
    pred = [sum(b[j] * X[i][j] for j in range(k)) for i in range(n)]
    my = sum(y) / n
    ss = sum((y[i] - pred[i]) ** 2 for i in range(n)); st = sum((v - my) ** 2 for v in y)
    return b, (1 - ss / st if st > 0 else 0.0), math.sqrt(ss / max(n - k, 1))


def korelasi(a, b):
    n = len(a); ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (sa * sb) if sa > 0 and sb > 0 else 0.0


def kuantil(v, q):
    s = sorted(v)
    if not s:
        return None
    x = q * (len(s) - 1); i = int(x); f = x - i
    return s[i] if i + 1 >= len(s) else s[i] * (1 - f) + s[i + 1] * f


def prospek_analog(oni, koef, sisa_sd, batas_tercile, hari_ini):
    """Prospek musim kebakaran Agu-Nov berikutnya dari tahun-tahun analog ENSO.
    oni: hasil baca_oni; koef = [a, b] untuk log10(titik + 1) = a + b * ONI_ASO; batas_tercile = (t33, t67) jumlah titik historis."""
    th, bl = hari_ini.year, hari_ini.month
    target = th if bl <= 8 else th + 1
    if (target, 'ASO') in oni:   # sudah teramati
        x = [oni[(target, 'ASO')]]; dasar = ('ASO', target); analog = []
    else:
        kunci = sorted((k for k in oni if k[0] >= target - 1), key=lambda k: (k[0], MUSIM.index(k[1])))
        ty, ms = kunci[-1]; nilai = oni[(ty, ms)]; geser = target - ty
        dasar = (ms, ty); lebar = 0.4; analog = []
        while len(analog) < 6 and lebar < 3.1:
            analog = [y for y in range(1950, ty) if (y, ms) in oni and abs(oni[(y, ms)] - nilai) <= lebar and (y + geser, 'ASO') in oni]
            lebar += 0.2
        x = [oni[(y + geser, 'ASO')] for y in analog]
    log_n = [koef[0] + koef[1] * v for v in x]
    # sebaran: tiap analog + ketidakpastian regresi (5 kuantil normal)
    z = [-1.2816, -0.5244, 0.0, 0.5244, 1.2816]
    semua = [10 ** (m + sisa_sd * q) - 1 for m in log_n for q in z]
    t33, t67 = batas_tercile
    n = float(len(semua))
    return {
        'musim_target': 'Agu-Nov %d' % target, 'dasar': '%s %d' % dasar, 'oni_dasar': oni.get((dasar[1], dasar[0])),
        'tahun_analog': analog, 'oni_aso_analog': [round(v, 2) for v in x],
        'oni_aso_median': round(kuantil(x, 0.5), 2), 'peluang_el_nino': round(sum(1 for v in x if v >= 0.5) / len(x), 2),
        'peluang_la_nina': round(sum(1 for v in x if v <= -0.5) / len(x), 2),
        'titik_p10': round(kuantil(semua, 0.1)), 'titik_median': round(kuantil(semua, 0.5)), 'titik_p90': round(kuantil(semua, 0.9)),
        'peluang_bawah_normal': round(sum(1 for v in semua if v < t33) / n, 2), 'peluang_normal': round(sum(1 for v in semua if t33 <= v <= t67) / n, 2),
        'peluang_atas_normal': round(sum(1 for v in semua if v > t67) / n, 2),
    }

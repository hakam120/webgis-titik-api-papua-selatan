#!/usr/bin/env python3
"""Pembaru prakiraan otomatis WebGIS Titik Api Papua Selatan (GitHub Actions, tanpa kunci akun, pustaka standar saja).

Tiga jangka waktu:
  1. Harian (16 hari)  : prakiraan cuaca Open-Meteo -> FWI harian di 23 titik iklim (peringatan dini).
  2. Musiman (6 bulan) : prakiraan musiman ensemble 51 anggota -> hujan, FWI, Drought Code bulanan (skenario kering/tengah/basah)
                         yang menjadi masukan model dinamis (Random Forest bulanan) di peramban.
  3. Tahunan (ENSO)    : indeks ONI NOAA + tahun-tahun analog -> prospek musim kebakaran Agu-Nov berikutnya.
Riwayat cuaca harian dilanjutkan dari arsip ERA5 (jeda +-5 hari) agar keadaan FWI bersambung.
Keluaran: data/prakiraan.js (window.PRAKIRAAN). Bila satu sumber gagal, bagian itu memakai data terakhir yang tersimpan.
"""
import datetime as dt, json, os, sys, time, traceback
import prakiraan_lib as L
import enso_lib as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DP = os.path.join(ROOT, 'data', 'prakiraan')
TITIK_MUSIM = [2, 4, 5, 7, 9, 11, 13, 15, 17, 20]   # subset titik untuk prakiraan musiman (hemat kuota API)
VAR_MUSIM = ['temperature_2m_max', 'relative_humidity_2m_min', 'wind_speed_10m_max', 'wind_speed_10m_mean', 'precipitation_sum']
HARI_MUSIM = 190
JEDA = float(os.environ.get('JEDA_API', '3'))
JEDA_MUSIM = float(os.environ.get('JEDA_MUSIM', '40'))
UMUR_MUSIM = int(os.environ.get('UMUR_MUSIM_HARI', '6'))
EPS = {'hujan': 5.0, 'hujan3': 15.0, 'fwi': 0.5, 'dc': 5.0}
IDS = [t[0] for t in L.TITIK]


def baca(nama, bawaan=None):
    p = os.path.join(DP, nama)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else bawaan


def tulis(nama, obj):
    json.dump(obj, open(os.path.join(DP, nama), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def hari_dalam_bulan(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.date(y, m, 1)).days


def bulan_plus(ym, k):
    y, m = int(ym[:4]), int(ym[5:7]) + k
    y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return '%04d-%02d' % (y, m)


def agregat_bulan(pasangan):
    """daftar (tanggal, fwi, dc, hujan) -> {ym: [hujan, jumlah fwi, jumlah dc, n]}"""
    o = {}
    for tg, fwi, dc, hujan in pasangan:
        g = o.setdefault(tg[:7], [0.0, 0.0, 0.0, 0]); g[0] += hujan; g[1] += fwi; g[2] += dc; g[3] += 1
    return o


def lanjutkan_arsip(H, hari_ini):
    """Tambah hari arsip baru (s.d. 6 hari lalu) ke riwayat bergulir dan majukan keadaan FWI."""
    awal = dt.date.fromisoformat(H['tanggal']) + dt.timedelta(days=1); akhir = hari_ini - dt.timedelta(days=6)
    if akhir < awal:
        return 0
    baru = {}; batas = akhir.isoformat()
    for pid, lon, lat in L.TITIK:
        deret = L.deret_harian(L.ambil_json(L.url_arsip(lon, lat, awal.isoformat(), akhir.isoformat()))['daily'])
        batas = min(batas, deret[-1][0]) if deret else ''
        baru[pid] = deret; time.sleep(JEDA)
    if batas < awal.isoformat():
        return 0
    for pid in IDS:
        hasil, keadaan = L.jalankan_fwi([x for x in baru[pid] if x[0] <= batas], tuple(H['keadaan'][str(pid)]))
        v = H['nilai'][str(pid)]
        for tg, fwi, dc, hujan, tm, rm in hasil:
            v['fwi'].append(round(fwi, 1)); v['dc'].append(round(dc)); v['hujan'].append(round(hujan, 1)); v['suhu'].append(round(tm, 1)); v['rh'].append(round(rm))
        for k in v:
            v[k] = v[k][-400:]
        H['keadaan'][str(pid)] = [round(x, 3) for x in keadaan]
    tambah = [x[0] for x in baru[IDS[0]] if x[0] <= batas]
    H['hari'] = (H['hari'] + tambah)[-400:]; H['tanggal'] = batas
    return len(tambah)


def prakiraan_harian(H, hari_ini):
    """FWI harian dari hari setelah arsip sampai 15 hari ke depan."""
    D = dt.date.fromisoformat(H['tanggal']); lalu = min(max((hari_ini - D).days - 1, 1), 92)
    deret_semua, keadaan_akhir = {}, {}
    for pid, lon, lat in L.TITIK:
        deret = [x for x in L.deret_harian(L.ambil_json(L.url_prakiraan(lon, lat, lalu, 16))['daily']) if x[0] > H['tanggal']]
        deret_semua[pid], keadaan_akhir[pid] = L.jalankan_fwi(deret, tuple(H['keadaan'][str(pid)]))
        time.sleep(JEDA)
    tanggal = sorted(set.intersection(*[set(h[0] for h in deret_semua[p]) for p in IDS]))
    peta = {p: {h[0]: h for h in deret_semua[p]} for p in IDS}
    ekor = H['hari'][-7:]; n = len(ekor)
    out = {'tanggal': ekor + tanggal,
           'jenis': ['arsip'] * n + ['analisis' if t < hari_ini.isoformat() else 'prakiraan' for t in tanggal],
           'fwi': [[H['nilai'][str(p)]['fwi'][-n + i] for p in IDS] for i in range(n)] + [[round(peta[p][t][1], 1) for p in IDS] for t in tanggal],
           'hujan': [[H['nilai'][str(p)]['hujan'][-n + i] for p in IDS] for i in range(n)] + [[round(peta[p][t][3], 1) for p in IDS] for t in tanggal]}
    for p in IDS:   # hanya hari yang ada di semua titik
        deret_semua[p] = [h for h in deret_semua[p] if h[0] <= tanggal[-1]]
    return out, deret_semua, keadaan_akhir


def amatan_per_titik(H, deret_semua):
    """Arsip + analisis + prakiraan 16 hari per titik -> {pid: {ym: [hujan, sum fwi, sum dc, n]}}"""
    o = {}
    for p in IDS:
        v = H['nilai'][str(p)]
        pas = [(H['hari'][i], v['fwi'][i], v['dc'][i], v['hujan'][i]) for i in range(len(H['hari']))]
        pas += [(h[0], h[1], h[2], h[3]) for h in deret_semua.get(p, [])]
        o[p] = agregat_bulan(pas)
    return o


def fitur_bulan(g):
    return {'hujan': g[0], 'fwi': g[1] / g[3], 'dc': g[2] / g[3]} if g and g[3] > 0 else None


def prakiraan_musiman(H, deret_semua, keadaan_akhir, dasar, hari_ini):
    """Anggota ensemble musiman -> fitur bulanan per skenario untuk semua titik iklim + ringkasan provinsi."""
    amat = amatan_per_titik(H, deret_semua)
    akhir_amat = max(h[0] for h in deret_semua[IDS[0]]) if deret_semua.get(IDS[0]) else H['tanggal']
    ym0 = hari_ini.isoformat()[:7]
    anggota = {}   # pid -> daftar anggota {ym: [hujan, sum fwi, sum dc, n]}
    for pid, lon, lat in L.TITIK:
        if pid not in TITIK_MUSIM:
            continue
        url = ('https://seasonal-api.open-meteo.com/v1/seasonal?latitude=%.4f&longitude=%.4f&forecast_days=%d&daily=%s&timezone=%s'
               % (lat, lon, HARI_MUSIM, ','.join(VAR_MUSIM), L.ZONA))
        d = L.ambil_json(url, coba=5, jeda=60)['daily']
        daftar = []
        for ak in [''] + ['_member%02d' % k for k in range(1, 60)]:
            if ('precipitation_sum' + ak) not in d:
                continue
            hasil, _ = L.jalankan_fwi([x for x in L.deret_harian(d, ak) if x[0] > akhir_amat], keadaan_akhir[pid])
            daftar.append(agregat_bulan([(h[0], h[1], h[2], h[3]) for h in hasil]))
        anggota[pid] = daftar; time.sleep(JEDA_MUSIM)
    n_ang = min(len(v) for v in anggota.values())
    if n_ang < 10:
        raise RuntimeError('anggota ensemble terlalu sedikit: %d' % n_ang)
    # bulan target: bulan berjalan s.d. bulan terakhir yang hampir lengkap
    bulan = []
    for k in range(0, 8):
        ym = bulan_plus(ym0, k)
        cukup = all(((amat[p].get(ym) or [0, 0, 0, 0])[3] + (anggota[p][0].get(ym) or [0, 0, 0, 0])[3]) >= 0.9 * hari_dalam_bulan(ym) for p in TITIK_MUSIM)
        if not cukup:
            break
        bulan.append(ym)
    # fitur per titik musiman, anggota, bulan (amatan + anggota)
    def gabung(p, a, ym):
        x = amat[p].get(ym) or [0.0, 0.0, 0.0, 0]; y = anggota[p][a].get(ym) or [0.0, 0.0, 0.0, 0]
        return fitur_bulan([x[i] + y[i] for i in range(4)])
    F = {p: [[gabung(p, a, ym) for ym in bulan] for a in range(n_ang)] for p in TITIK_MUSIM}
    for p in TITIK_MUSIM:
        for a in range(n_ang):
            for j, ym in enumerate(bulan):
                h3 = 0.0
                for k in (1, 2, 3):
                    if j - k >= 0:
                        h3 += F[p][a][j - k]['hujan']
                    else:
                        g = amat[p].get(bulan_plus(ym, -k)); h3 += g[0] if g else dasar['titik'][str(p)]['hujan'][(int(ym[5:7]) - 1 - k) % 12]
                F[p][a][j]['hujan3'] = h3
    # skenario per bulan: urutkan anggota menurut hujan rata-rata titik musiman
    kelompok = {'kering': (0.0, 0.2), 'tengah': (0.4, 0.6), 'basah': (0.8, 1.0)}
    sk = {s: {k: [] for k in EPS} for s in kelompok}
    prov = {k: [] for k in ('hujan_p10', 'hujan_med', 'hujan_p90', 'hujan_normal', 'fwi_p10', 'fwi_med', 'fwi_p90', 'fwi_normal', 'p_kering', 'p_normal', 'p_basah')}
    jarak = {p: sorted(((L.TITIK[IDS.index(q)][1] - L.TITIK[IDS.index(p)][1]) ** 2 + (L.TITIK[IDS.index(q)][2] - L.TITIK[IDS.index(p)][2]) ** 2, q) for q in TITIK_MUSIM)[:2] for p in IDS}
    for j, ym in enumerate(bulan):
        b = int(ym[5:7]) - 1
        hp = [sum(F[p][a][j]['hujan'] for p in TITIK_MUSIM) / len(TITIK_MUSIM) for a in range(n_ang)]
        fp = [sum(F[p][a][j]['fwi'] for p in TITIK_MUSIM) / len(TITIK_MUSIM) for a in range(n_ang)]
        urut = sorted(range(n_ang), key=lambda a: hp[a])
        pv = dasar['provinsi']
        prov['hujan_p10'].append(round(E.kuantil(hp, 0.1), 1)); prov['hujan_med'].append(round(E.kuantil(hp, 0.5), 1)); prov['hujan_p90'].append(round(E.kuantil(hp, 0.9), 1))
        prov['fwi_p10'].append(round(E.kuantil(fp, 0.1), 2)); prov['fwi_med'].append(round(E.kuantil(fp, 0.5), 2)); prov['fwi_p90'].append(round(E.kuantil(fp, 0.9), 2))
        prov['hujan_normal'].append(pv['hujan'][b]); prov['fwi_normal'].append(pv['fwi'][b])
        prov['p_kering'].append(round(sum(1 for v in hp if v < pv['hujan_t33'][b]) / n_ang, 2)); prov['p_basah'].append(round(sum(1 for v in hp if v > pv['hujan_t67'][b]) / n_ang, 2))
        prov['p_normal'].append(round(1 - prov['p_kering'][-1] - prov['p_basah'][-1], 2))
        for s, (q0, q1) in kelompok.items():
            pilih = urut[int(q0 * n_ang):max(int(q1 * n_ang), int(q0 * n_ang) + 1)]
            rata = {p: {k: sum(F[p][a][j][k] for a in pilih) / len(pilih) for k in EPS} for p in TITIK_MUSIM}
            for k in EPS:
                baris = []
                for p in IDS:
                    if p in rata:
                        baris.append(round(rata[p][k], 1)); continue
                    # titik lain: rasio terhadap normal dari 2 titik musiman terdekat (IDW), diterapkan ke normal titik itu
                    def normal(q):
                        t = dasar['titik'][str(q)]
                        return sum(t['hujan'][(b - i) % 12] for i in (1, 2, 3)) if k == 'hujan3' else t[k][b]
                    w = [1.0 / (d2 + 1e-6) for d2, _ in jarak[p]]
                    rasio = sum(wi * (rata[q][k] + EPS[k]) / (normal(q) + EPS[k]) for wi, (_, q) in zip(w, jarak[p])) / sum(w)
                    baris.append(round(max((normal(p) + EPS[k]) * rasio - EPS[k], 0.0), 1))
                sk[s][k].append(baris)
    return {'dibuat': hari_ini.isoformat(), 'anggota': n_ang, 'bulan': bulan, 'skenario': sk, 'provinsi': prov,
            'catatan': 'Bulan berjalan = amatan + prakiraan 16 hari + anggota ensemble untuk sisa bulan.'}


def amatan_bulanan(H, dasar, n=8):
    """Fitur bulanan teramati (bulan lengkap pada arsip) per titik untuk pemantauan."""
    agg = {p: agregat_bulan([(H['hari'][i], H['nilai'][str(p)]['fwi'][i], H['nilai'][str(p)]['dc'][i], H['nilai'][str(p)]['hujan'][i]) for i in range(len(H['hari']))]) for p in IDS}
    lengkap = sorted(ym for ym, g in agg[IDS[0]].items() if g[3] >= hari_dalam_bulan(ym))
    bulan = [ym for ym in lengkap if all(bulan_plus(ym, -k) in lengkap for k in (1, 2, 3))][-n:]
    o = {'bulan': bulan, 'hujan': [], 'hujan3': [], 'fwi': [], 'dc': []}
    for ym in bulan:
        o['hujan'].append([round(agg[p][ym][0], 1) for p in IDS]); o['fwi'].append([round(agg[p][ym][1] / agg[p][ym][3], 1) for p in IDS])
        o['dc'].append([round(agg[p][ym][2] / agg[p][ym][3]) for p in IDS]); o['hujan3'].append([round(sum(agg[p][bulan_plus(ym, -k)][0] for k in (1, 2, 3)), 1) for p in IDS])
    return o


def main():
    sekarang = dt.datetime.now(dt.timezone.utc); hari_ini = (sekarang + dt.timedelta(hours=9)).date()
    H = baca('harian_terkini.json'); dasar = baca('dasar_iklim.json'); enso_model = baca('enso_model.json')
    lama = {}
    pj = os.path.join(ROOT, 'data', 'prakiraan.js')
    if os.path.exists(pj):
        s = open(pj, encoding='utf-8').read(); lama = json.loads(s[s.index('{'):s.rindex('}') + 1])
    out = {'dibuat_utc': sekarang.strftime('%Y-%m-%dT%H:%MZ'), 'titik': [list(t) for t in L.TITIK], 'titik_musiman': TITIK_MUSIM, 'status': {}}
    # 1. arsip
    try:
        n = lanjutkan_arsip(H, hari_ini)
        if n:
            tulis('harian_terkini.json', H)
        out['status']['arsip'] = 'ok (+%d hari)' % n
    except Exception as e:
        out['status']['arsip'] = 'gagal: %s' % e; traceback.print_exc()
    out['arsip_sampai'] = H['tanggal']; out['amatan_bulanan'] = amatan_bulanan(H, dasar)
    # 2. prakiraan harian
    deret_semua = keadaan_akhir = None
    try:
        out['harian'], deret_semua, keadaan_akhir = prakiraan_harian(H, hari_ini); out['status']['harian'] = 'ok'
    except Exception as e:
        out['harian'] = lama.get('harian'); out['status']['harian'] = 'gagal, memakai data terakhir: %s' % e; traceback.print_exc()
    # 3. prakiraan musiman (diperbarui bila sudah berumur >= UMUR_MUSIM hari atau bulan berganti)
    mus = baca('musiman_terakhir.json')
    perlu = mus is None or (hari_ini - dt.date.fromisoformat(mus['dibuat'])).days >= UMUR_MUSIM or mus['dibuat'][:7] != hari_ini.isoformat()[:7]
    if perlu and deret_semua is not None:
        try:
            mus = prakiraan_musiman(H, deret_semua, keadaan_akhir, dasar, hari_ini); tulis('musiman_terakhir.json', mus); out['status']['musiman'] = 'ok (diperbarui)'
        except Exception as e:
            out['status']['musiman'] = 'gagal, memakai data terakhir: %s' % e; traceback.print_exc()
    else:
        out['status']['musiman'] = 'memakai prakiraan %s' % (mus['dibuat'] if mus else '-')
    out['musiman'] = mus
    # 4. ENSO
    try:
        oni = E.baca_oni(E.unduh_teks(E.URL_ONI))
        kunci = sorted(oni, key=lambda k: (k[0], E.MUSIM.index(k[1])))[-24:]
        out['enso'] = {'oni': [[k[0], k[1], oni[k]] for k in kunci],
                       'prospek': E.prospek_analog(oni, enso_model['koef_oni'], enso_model['sisa_sd_oni'], enso_model['tercile'], hari_ini),
                       'model': {k: enso_model[k] for k in ('tahun', 'titik_agu_nov', 'oni_aso', 'koef_oni', 'r2_oni', 'r_sisih_satu_tahun', 'tercile', 'median', 'titik_2026_agu_nov')}}
        out['status']['enso'] = 'ok'
    except Exception as e:
        out['enso'] = lama.get('enso'); out['status']['enso'] = 'gagal, memakai data terakhir: %s' % e; traceback.print_exc()
    # 5. catatan verifikasi: prakiraan hujan provinsi bulan depan vs amatan setelah bulan itu lengkap
    ver = baca('verifikasi.json', [])
    if mus and len(mus['bulan']) > 1:
        kunci = mus['dibuat'][:7] + '>' + mus['bulan'][1]
        ver = [v for v in ver if v['kunci'] != kunci] + [{'kunci': kunci, 'dibuat': mus['dibuat'], 'target': mus['bulan'][1], 'hujan_med': mus['provinsi']['hujan_med'][1],
                                                         'hujan_p10': mus['provinsi']['hujan_p10'][1], 'hujan_p90': mus['provinsi']['hujan_p90'][1], 'hujan_normal': mus['provinsi']['hujan_normal'][1]}]
    ab = out['amatan_bulanan']
    for v in ver:
        if v['target'] in ab['bulan']:
            j = ab['bulan'].index(v['target']); v['hujan_amatan'] = round(sum(ab['hujan'][j][IDS.index(p)] for p in TITIK_MUSIM) / len(TITIK_MUSIM), 1)
    ver = ver[-60:]; tulis('verifikasi.json', ver); out['verifikasi'] = ver
    with open(pj, 'w', encoding='utf-8') as f:
        f.write('window.PRAKIRAAN = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
    print(json.dumps(out['status'], ensure_ascii=False)); print('arsip s.d.', out['arsip_sampai'], '| musiman:', mus['bulan'] if mus else None)
    return 0


if __name__ == '__main__':
    sys.exit(main())

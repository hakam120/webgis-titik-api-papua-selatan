# WebGIS Titik Api & Bahaya Kebakaran Provinsi Papua Selatan

WebGIS PjBL GD4103 Sistem Informasi Geografis 2026 (Teknik Geodesi dan Geomatika ITB), kelompok **K05 · Kelompok 3**, tema karhutla dengan fokus **titik api**.

**Buka WebGIS:** https://hakam120.github.io/webgis-titik-api-papua-selatan/

## Isi

| Tab | Isi |
|---|---|
| Terkini | Titik api NASA FIRMS 7 hari terakhir (VIIRS S-NPP, NOAA-20, NOAA-21, MODIS), per hari, kabupaten, kecamatan, kelas bahaya, gambut, fungsi kawasan, perizinan, dan kelas rawan KLHK. Diperbarui otomatis tiap 6 jam. |
| Lapisan | Model bahaya v2 (Random Forest, Rasio Frekuensi, AHP), area terbakar 2026 (MODIS MCD64A1), anomali hujan 2026 (CHIRPS), kehilangan hutan 2024–2025 (Hansen), frekuensi terbakar 2015–2025, Peta Rawan Karhutla KLHK, gambut FEG, fungsi kawasan hutan, perizinan, penduduk, kecamatan dengan statistik dampak. |
| Pemodelan | Hitung ulang model AHP/FR 12 parameter langsung di peramban (grid 1 km) dan lihat pengaruhnya pada AUC. |
| Statistik | AUC per model dan per data uji, kurva tingkat keberhasilan, kepentingan parameter Random Forest, deret bulanan titik api 2015–2026, dampak per kabupaten dan kecamatan. |

## Pembaruan otomatis

Workflow `.github/workflows/perbarui-dan-terbitkan.yml` menjalankan `scripts/perbarui_titik_api.py` setiap 6 jam:

1. mengunduh CSV FIRMS NRT 7 hari (publik, tanpa MAP_KEY);
2. menyaring titik di Provinsi Papua Selatan dan memberi atribut dari grid acuan `data/acuan_0005.bin.gz` (0,005°, dibuat dari raster 100 m);
3. menulis `data/titik_api_7hari.js` dan menambah `data/arsip_harian.js`;
4. menerbitkan ulang situs ke GitHub Pages.

Pembaruan manual: tab **Actions** → *Perbarui titik api & terbitkan WebGIS* → **Run workflow**.

## Menjalankan secara lokal

Buka `index.html` melalui server lokal (misalnya `jalankan_server_lokal.ps1` di Windows, lalu buka `http://localhost:8765`).

## Sumber data & lisensi

NASA FIRMS; MODIS MCD64A1 (NASA LP DAAC via Microsoft Planetary Computer); BIG Satu Peta / KLHK; ESA WorldCover 2021 (CC BY 4.0); Esri/Impact Observatory LULC; Hansen/UMD Global Forest Change v1.13 (CC BY 4.0); JRC Global Surface Water; CHIRPS v3; Copernicus DEM GLO-30; Peat-ML (CC BY 4.0); GHSL GHS-BUILT-S 2025; WorldPop 2020 (CC BY 4.0) dan Sensus Penduduk 2020 (BPS); © kontributor OpenStreetMap (ODbL); geoBoundaries. Peta dasar © Esri dan © OpenStreetMap.

Produk akademik, bukan peta resmi pemerintah. Titik api adalah indikasi anomali panas dari satelit, bukan konfirmasi kebakaran di lapangan.

Tim: Rizki Maulana (15123070), Muhammad Hakam Al-Asyam (15123044), Nurrachman Alwy Sumintardja (15123100), Hafzulh Usmu Alfalah (12823048), Fauzan Rizki (12823030).

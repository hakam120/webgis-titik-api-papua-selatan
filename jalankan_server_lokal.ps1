# jalankan_server_lokal.ps1
# Server web statis sederhana untuk mencoba WebGIS di komputer sendiri (tanpa instalasi).
# Cara pakai: klik kanan > Run with PowerShell, atau
#   powershell -ExecutionPolicy Bypass -File .\jalankan_server_lokal.ps1
# lalu buka http://localhost:8765/ di peramban. Tekan Ctrl+C untuk berhenti.
param([int]$Port = 8765)
$root = $PSScriptRoot
$types = @{ '.html' = 'text/html; charset=utf-8'; '.js' = 'application/javascript; charset=utf-8'; '.json' = 'application/json'; '.geojson' = 'application/geo+json'; '.png' = 'image/png'; '.css' = 'text/css'; '.ico' = 'image/x-icon' }
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()
Write-Host "WebGIS berjalan di http://localhost:$Port/  (Ctrl+C untuk berhenti)"
try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        try {   # satu permintaan gagal (mis. koneksi diputus peramban) tidak menghentikan server
            $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
            if ([string]::IsNullOrEmpty($rel)) { $rel = 'index.html' }
            $path = [IO.Path]::GetFullPath((Join-Path $root $rel))
            if ($path.StartsWith($root) -and (Test-Path $path -PathType Leaf)) {
                $bytes = [IO.File]::ReadAllBytes($path)
                $ext = [IO.Path]::GetExtension($path).ToLower()
                $ctx.Response.ContentType = $(if ($types.ContainsKey($ext)) { $types[$ext] } else { 'application/octet-stream' })
                $ctx.Response.ContentLength64 = $bytes.Length
                if ($ctx.Request.HttpMethod -ne 'HEAD') { $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length) }
            } else { $ctx.Response.StatusCode = 404 }
        } catch { Write-Host "  galat permintaan $($ctx.Request.Url.AbsolutePath): $($_.Exception.Message)" }
        try { $ctx.Response.Close() } catch { }
    }
} finally { $listener.Stop() }

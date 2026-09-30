# install.ps1 - Installer findref untuk Windows 10/11 (PowerShell 5.1+ atau 7+)
#
# Alur (sama seperti instalasi manual yang benar):
#   1. clone repo        -> %LOCALAPPDATA%\findref\app\src   (atau unduh zip jika git tidak ada)
#   2. buat virtualenv   -> %LOCALAPPDATA%\findref\app\venv
#   3. install package   -> pip di dalam venv (tidak menyentuh Python sistem)
#   4. buat perintah     -> %LOCALAPPDATA%\findref\app\bin\findref.cmd  (ditambahkan ke PATH user)
#
# (Config, cache, dan log findref sendiri disimpan terpisah di %LOCALAPPDATA%\findref,
#  supaya --uninstall tidak pernah ikut menghapusnya - lihat `findref doctor`.)
#
# Pemakaian dengan curl (bawaan Windows 10/11) - jalankan di CMD atau PowerShell:
#
#   curl.exe -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.ps1 -o install.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
#
# Catatan: tulis "curl.exe" (bukan "curl") karena di PowerShell "curl" adalah alias
# Invoke-WebRequest yang perilakunya berbeda.
#
# Dari folder hasil clone:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install\install.ps1
#
# Opsi (lewat environment variable):
#   $env:FINDREF_HOME         Lokasi instalasi (default: %LOCALAPPDATA%\findref\app)
#   $env:FINDREF_REPO_URL     URL repo git (default: repo resmi)
#   $env:FINDREF_REPO_BRANCH  Branch (default: main)
#   $env:FINDREF_DEV=1        Mode editable (butuh source lokal)
#   $env:FINDREF_UNINSTALL=1  Hapus instalasi findref
#
# Skrip ini TIDAK meminta konfirmasi, jadi aman dipakai non-interaktif.
# File ini sengaja ASCII-only agar tidak rusak di PowerShell 5.1.

# ---------------------------------------------------------------------- #
# Argumen (opsional: dipakai saat script dijalankan lokal dengan -File;
# $env:FINDREF_UNINSTALL tetap didukung untuk pemakaian "irm | iex" yang
# tidak bisa membawa argumen baris perintah)
# ---------------------------------------------------------------------- #
param([switch]$Uninstall)

# ---------------------------------------------------------------------- #
# Konfigurasi
# ---------------------------------------------------------------------- #

$RepoUrl    = if ($env:FINDREF_REPO_URL)    { $env:FINDREF_REPO_URL }    else { "https://github.com/farisalfatih/find_references_scopus.git" }
$RepoBranch = if ($env:FINDREF_REPO_BRANCH) { $env:FINDREF_REPO_BRANCH } else { "main" }
# NOTE: findref's config/cache/log files live at %LOCALAPPDATA%\findref (via `platformdirs`,
# see config/defaults.py). The program itself installs one level deeper, in ...\findref\app,
# so that `--uninstall` (or `findref uninstall`) can remove the program without also wiping
# your config.toml and accounts - the two folders must NOT be the same.
$InstallHome = if ($env:FINDREF_HOME)       { $env:FINDREF_HOME }        else { Join-Path $env:LOCALAPPDATA "findref\app" }
$DevMode    = ($env:FINDREF_DEV -eq "1")
$Uninstall  = $Uninstall.IsPresent -or ($env:FINDREF_UNINSTALL -eq "1")

$SrcDir  = Join-Path $InstallHome "src"
$VenvDir = Join-Path $InstallHome "venv"
$BinDir  = Join-Path $InstallHome "bin"
$VenvPy  = Join-Path $VenvDir "Scripts\python.exe"

# TLS 1.2 untuk Windows PowerShell 5.1 (agar bisa unduh dari GitHub)
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

# ---------------------------------------------------------------------- #
# Helper
# ---------------------------------------------------------------------- #

function Write-Info([string]$m) { Write-Host "[findref] $m" -ForegroundColor Cyan }
function Write-Ok([string]$m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Write-Err([string]$m)  { Write-Host "[X] $m" -ForegroundColor Red }

function Stop-Install([string]$m) {
    Write-Err $m
    exit 1
}

# Jalankan program native, kembalikan exit code. Tidak memakai $ErrorActionPreference=Stop
# karena PowerShell 5.1 menganggap output stderr (mis. progress git) sebagai error.
function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Exe @Arguments
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

function Test-PythonCandidate {
    # Mengembalikan hashtable (Exe, PreArgs, Version) bila Python >= 3.10, selain itu $null
    param([string]$Exe, [string[]]$PreArgs)
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $out = & $Exe @PreArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        if ($code -eq 0 -and "$out" -match "^(\d+)\.(\d+)$") {
            $maj = [int]$Matches[1]
            $min = [int]$Matches[2]
            if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 10)) {
                return @{ Exe = $Exe; PreArgs = $PreArgs; Version = "$maj.$min" }
            }
        }
    } catch { }
    return $null
}

# ---------------------------------------------------------------------- #
# Uninstall
# ---------------------------------------------------------------------- #

if ($Uninstall) {
    Write-Info "Menghapus findref..."
    if (Test-Path $InstallHome) {
        Remove-Item -Recurse -Force $InstallHome
        Write-Ok "Hapus $InstallHome"
    }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath) {
        $parts = $userPath.Split(";") | Where-Object { $_ -and ($_.TrimEnd("\") -ne $BinDir.TrimEnd("\")) }
        [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
        Write-Ok "Hapus $BinDir dari PATH user"
    }
    Write-Info "Selesai. Konfigurasi & data (SCImago, cache, log), jika ada, di %LOCALAPPDATA%\findref TIDAK dihapus."
    Write-Host "  Untuk menghapus itu juga, jalankan: findref uninstall --purge   (sebelum langkah di atas)"
    Write-Host "  Atau hapus manual: findref doctor   # menampilkan semua path yang dipakai"
    exit 0
}

# ---------------------------------------------------------------------- #
# Python >= 3.10
# ---------------------------------------------------------------------- #

Write-Info "Mencari Python 3.10+ ..."

$Py = $null
$candidates = @(
    @{ Exe = "py";      PreArgs = @("-3") },
    @{ Exe = "python";  PreArgs = @() },
    @{ Exe = "python3"; PreArgs = @() }
)
foreach ($c in $candidates) {
    if (Get-Command $c.Exe -ErrorAction SilentlyContinue) {
        $Py = Test-PythonCandidate -Exe $c.Exe -PreArgs $c.PreArgs
        if ($Py) { break }
    }
}

if (-not $Py) {
    Write-Err "Python 3.10+ tidak ditemukan."
    Write-Host ""
    Write-Host "Install Python lalu jalankan ulang skrip ini:"
    Write-Host "  winget install -e --id Python.Python.3.12"
    Write-Host "  atau unduh dari https://www.python.org/downloads/ (centang 'Add python.exe to PATH')"
    Write-Host ""
    Write-Host "Setelah install, TUTUP lalu buka lagi terminal."
    exit 1
}
Write-Ok "Python $($Py.Version) ($($Py.Exe))"

# ---------------------------------------------------------------------- #
# Ambil source: lokal (jika dijalankan dari repo) atau clone / unduh zip
# ---------------------------------------------------------------------- #

$Source = $null
$scriptDir = $null
if ($PSScriptRoot) { $scriptDir = $PSScriptRoot }
elseif ($MyInvocation.MyCommand.Path) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }

if ($scriptDir) {
    $parent = Split-Path -Parent $scriptDir
    if ($parent -and (Test-Path (Join-Path $parent "pyproject.toml"))) {
        $Source = $parent
        Write-Info "Memakai source lokal: $Source"
    }
}

if (-not $Source) {
    if ($DevMode) {
        Stop-Install "Mode FINDREF_DEV=1 butuh source lokal. Clone repo dulu, lalu jalankan .\install\install.ps1"
    }

    New-Item -ItemType Directory -Force -Path $InstallHome | Out-Null

    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $SrcDir ".git")) {
            Write-Info "Memperbarui source di $SrcDir"
            $c1 = Invoke-Native "git" @("-C", $SrcDir, "fetch", "--depth", "1", "origin", $RepoBranch)
            if ($c1 -ne 0) { Stop-Install "git fetch gagal. Hapus folder $SrcDir lalu ulangi." }
            $c2 = Invoke-Native "git" @("-C", $SrcDir, "reset", "--hard", "FETCH_HEAD")
            if ($c2 -ne 0) { Stop-Install "git reset gagal. Hapus folder $SrcDir lalu ulangi." }
        } else {
            if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
            Write-Info "Clone $RepoUrl (branch $RepoBranch)"
            $c = Invoke-Native "git" @("clone", "--quiet", "--depth", "1", "-b", $RepoBranch, $RepoUrl, $SrcDir)
            if ($c -ne 0) { Stop-Install "Gagal clone repo. Periksa koneksi internet / nama branch." }
        }
    } else {
        Write-Warn "git tidak ditemukan - mengunduh zip dari GitHub."
        $base = $RepoUrl -replace "\.git$", ""
        $zipUrl  = "$base/archive/refs/heads/$RepoBranch.zip"
        $zipFile = Join-Path $env:TEMP "findref-src.zip"
        $tmpDir  = Join-Path $env:TEMP "findref-src-extract"
        try {
            if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
            Invoke-WebRequest -UseBasicParsing -Uri $zipUrl -OutFile $zipFile
            Expand-Archive -Path $zipFile -DestinationPath $tmpDir -Force
            $inner = Get-ChildItem $tmpDir | Select-Object -First 1
            if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
            Move-Item -Path $inner.FullName -Destination $SrcDir
            Remove-Item -Force $zipFile -ErrorAction SilentlyContinue
            Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
        } catch {
            Stop-Install "Gagal mengunduh $zipUrl : $($_.Exception.Message)"
        }
    }

    if (-not (Test-Path (Join-Path $SrcDir "pyproject.toml"))) {
        Stop-Install "pyproject.toml tidak ada di $SrcDir - repo/branch salah?"
    }
    $Source = $SrcDir
    Write-Ok "Source siap: $Source"
}

# ---------------------------------------------------------------------- #
# Buat virtualenv
# ---------------------------------------------------------------------- #

New-Item -ItemType Directory -Force -Path $InstallHome | Out-Null
if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir }

Write-Info "Membuat virtualenv di $VenvDir"
$venvArgs = @()
$venvArgs += $Py.PreArgs
$venvArgs += @("-m", "venv", $VenvDir)
$c = Invoke-Native $Py.Exe $venvArgs
if ($c -ne 0 -or -not (Test-Path $VenvPy)) { Stop-Install "Gagal membuat virtualenv." }
Write-Ok "Virtualenv dibuat"

# ---------------------------------------------------------------------- #
# Install package di dalam venv
# (memanggil python venv langsung = sama efeknya dengan Activate.ps1 lalu pip)
# ---------------------------------------------------------------------- #

Write-Info "Memperbarui pip di dalam venv..."
$c = Invoke-Native $VenvPy @("-m", "pip", "install", "--quiet", "--upgrade", "pip", "setuptools", "wheel")
if ($c -ne 0) { Stop-Install "Gagal memperbarui pip." }

Write-Info "Menginstall findref dan dependensinya..."
if ($DevMode) {
    $c = Invoke-Native $VenvPy @("-m", "pip", "install", "--editable", $Source)
} else {
    $c = Invoke-Native $VenvPy @("-m", "pip", "install", $Source)
}
if ($c -ne 0) { Stop-Install "pip install gagal." }
Write-Ok "Package ter-install"

# ---------------------------------------------------------------------- #
# Buat perintah findref (shim .cmd) + PATH user
# ---------------------------------------------------------------------- #

$exe = Join-Path $VenvDir "Scripts\findref.exe"
if (-not (Test-Path $exe)) { Stop-Install "findref.exe tidak ditemukan di $exe" }

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$shim = "@echo off`r`n`"$exe`" %*`r`n"
foreach ($name in @("findref", "find-refs")) {
    [IO.File]::WriteAllText((Join-Path $BinDir "$name.cmd"), $shim, [Text.Encoding]::ASCII)
}
Write-Ok "Perintah dibuat di $BinDir"

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
$already = $userPath.Split(";") | Where-Object { $_.TrimEnd("\") -eq $BinDir.TrimEnd("\") }
$needReopen = $false
if (-not $already) {
    $newPath = if ($userPath) { $userPath.TrimEnd(";") + ";" + $BinDir } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $needReopen = $true
    Write-Ok "PATH user diperbarui"
}
if (-not (($env:Path).Split(";") | Where-Object { $_.TrimEnd("\") -eq $BinDir.TrimEnd("\") })) {
    $env:Path = "$env:Path;$BinDir"
}

# ---------------------------------------------------------------------- #
# Verifikasi
# ---------------------------------------------------------------------- #

$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$verOut = & $exe --version 2>&1
$verCode = $LASTEXITCODE
$ErrorActionPreference = $prev
if ($verCode -ne 0) {
    Stop-Install "Instalasi selesai tetapi 'findref --version' gagal. Coba: $VenvPy -m find_references_scopus --version"
}
Write-Ok "$verOut"

Write-Host ""
Write-Info "Instalasi selesai!"
if ($needReopen) {
    Write-Host "  TUTUP lalu buka lagi terminal agar perintah 'findref' dikenali."
    Write-Host ""
}
Write-Host "Langkah berikutnya:"
Write-Host "  findref setup     # Konfigurasi API key (interaktif)"
Write-Host "  findref doctor    # Diagnosa instalasi"
Write-Host "  findref guide     # Panduan penggunaan"
Write-Host ""
Write-Host "Perbarui nanti dengan menjalankan ulang perintah instalasi yang sama."
Write-Host "Hapus dengan: `$env:FINDREF_UNINSTALL=1; .\install.ps1"
Write-Host ""

exit 0

#!/usr/bin/env bash
#
# install.sh - Installer findref untuk Linux / macOS / WSL / Git Bash
#
# Alur (sama seperti instalasi manual yang benar):
#   1. clone repo        -> $FINDREF_HOME/src
#   2. buat virtualenv   -> $FINDREF_HOME/venv
#   3. install package   -> pip di dalam venv (tidak menyentuh paket sistem)
#   4. buat perintah     -> ~/.local/bin/findref (symlink ke venv)
#
# (Config, cache, dan log findref sendiri disimpan terpisah, di ~/.config/findref
#  dkk. - lihat `findref doctor` - supaya --uninstall tidak pernah ikut menghapusnya.)
#
# Pemakaian (satu baris):
#   curl -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.sh | bash
#
# Atau dari folder hasil clone:
#   bash install/install.sh [opsi]
#
# Opsi:
#   --dev              Install mode editable (untuk pengembang)
#   --dir PATH         Lokasi instalasi (default: ~/.findref)
#   --branch NAMA      Branch yang di-clone (default: main)
#   --repo URL         URL repo git (default: repo resmi)
#   --no-modify-path   Jangan ubah ~/.bashrc / ~/.zshrc
#   --uninstall        Hapus instalasi findref (config/cache/log TIDAK dihapus;
#                       pakai `findref uninstall --purge` untuk itu)
#   -h, --help         Tampilkan bantuan ini
#
# Environment variable (alternatif opsi; FINDREF_UNINSTALL setara --uninstall,
# berguna saat skrip dipakai lewat `curl | bash` tanpa argumen tambahan):
#   FINDREF_HOME, FINDREF_REPO_URL, FINDREF_REPO_BRANCH, FINDREF_UNINSTALL=1
#
# Skrip ini TIDAK meminta konfirmasi, sehingga aman dipakai lewat `curl | bash`.
#
# Catatan: virtualenv tidak perlu di-"activate" di dalam skrip. Memanggil
# $VENV/bin/python -m pip ... sama persis efeknya dengan `source activate` lalu
# `pip ...`, tetapi tidak bergantung pada shell yang sedang dipakai.

set -euo pipefail

# ---------------------------------------------------------------------- #
# Konfigurasi
# ---------------------------------------------------------------------- #

REPO_URL="${FINDREF_REPO_URL:-https://github.com/farisalfatih/find_references_scopus.git}"
REPO_BRANCH="${FINDREF_REPO_BRANCH:-main}"
INSTALL_HOME="${FINDREF_HOME:-$HOME/.findref}"
BIN_DIR="$HOME/.local/bin"
DEV_MODE=false
MODIFY_PATH=true
# Also honor $FINDREF_UNINSTALL=1 (parity with install.ps1's $env:FINDREF_UNINSTALL,
# useful when the script is piped straight into bash without extra arguments).
UNINSTALL=false
[[ "${FINDREF_UNINSTALL:-}" == "1" ]] && UNINSTALL=true

# ---------------------------------------------------------------------- #
# Warna & log
# ---------------------------------------------------------------------- #

if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
    BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

log()  { echo -e "${BLUE}[findref]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[X]${NC} $*" >&2; }
die()  { err "$*"; exit 1; }

# ---------------------------------------------------------------------- #
# Argumen
# ---------------------------------------------------------------------- #

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dev)            DEV_MODE=true; shift ;;
        --dir)            [[ $# -ge 2 ]] || die "--dir butuh nilai"; INSTALL_HOME="$2"; shift 2 ;;
        --branch)         [[ $# -ge 2 ]] || die "--branch butuh nilai"; REPO_BRANCH="$2"; shift 2 ;;
        --repo)           [[ $# -ge 2 ]] || die "--repo butuh nilai"; REPO_URL="$2"; shift 2 ;;
        --no-modify-path) MODIFY_PATH=false; shift ;;
        --uninstall)      UNINSTALL=true; shift ;;
        -h|--help)
            if [[ -f "${BASH_SOURCE[0]:-}" ]]; then
                grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            else
                echo "Lihat https://github.com/farisalfatih/find_references_scopus untuk bantuan."
            fi
            exit 0
            ;;
        *) die "Opsi tidak dikenal: $1 (gunakan --help)" ;;
    esac
done

SRC_DIR="$INSTALL_HOME/src"
VENV_DIR="$INSTALL_HOME/venv"
VENV_PY="$VENV_DIR/bin/python"

# ---------------------------------------------------------------------- #
# Uninstall
# ---------------------------------------------------------------------- #

if [[ "$UNINSTALL" == "true" ]]; then
    log "Menghapus findref..."
    for name in findref find-refs; do
        link="$BIN_DIR/$name"
        if [[ -L "$link" ]]; then rm -f "$link"; ok "Hapus $link"; fi
    done
    if [[ -d "$INSTALL_HOME" ]]; then
        rm -rf "$INSTALL_HOME"
        ok "Hapus $INSTALL_HOME"
    fi
    # Hapus baris "# findref" + "export PATH=..." yang ditambahkan skrip ini ke rc files
    # (marker yang sama dipakai oleh `findref uninstall`, lihat commands/uninstall.py).
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [[ -f "$rc" ]] && grep -qsF "# findref" "$rc"; then
            # Mirror strip_path_block() in commands/uninstall.py: drop the "# findref"
            # line, the "export PATH=..." line right after it (only if it's actually
            # there), and one blank line immediately before the marker (if any).
            # A 1-line output buffer lets us drop that trailing blank line once we
            # know a marker follows it.
            awk '
                /^# findref$/ {
                    if (have_pending && pending == "") { have_pending = 0 }
                    else if (have_pending) { print pending; have_pending = 0 }
                    after_marker = 1
                    next
                }
                after_marker {
                    after_marker = 0
                    if ($0 ~ /^export PATH=/) next
                }
                { if (have_pending) print pending; pending = $0; have_pending = 1 }
                END { if (have_pending) print pending }
            ' "$rc" > "$rc.findref-tmp" && mv "$rc.findref-tmp" "$rc"
            ok "Baris PATH dihapus dari $rc"
        fi
    done
    log "Selesai. Konfigurasi & data (SCImago, cache, log), jika ada, TIDAK dihapus."
    echo "  Untuk menghapus itu juga, jalankan: findref uninstall --purge   (sebelum langkah di atas)"
    echo "  Atau hapus manual: findref doctor   # menampilkan semua path yang dipakai"
    exit 0
fi

# ---------------------------------------------------------------------- #
# Deteksi platform
# ---------------------------------------------------------------------- #

OS="$(uname -s)"
case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    MINGW*|MSYS*|CYGWIN*)
        die "Terdeteksi Windows (Git Bash/MSYS). Gunakan install.ps1 di PowerShell/CMD." ;;
    *) die "OS tidak didukung: $OS" ;;
esac
log "Platform: $PLATFORM ($(uname -m))"

# ---------------------------------------------------------------------- #
# Python >= 3.10
# ---------------------------------------------------------------------- #

PYTHON_BIN=""
for cmd in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PYTHON_BIN="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    err "Python 3.10+ tidak ditemukan."
    if [[ "$PLATFORM" == "macos" ]]; then
        echo "  brew install python@3.12"
    else
        echo "  sudo apt install -y python3 python3-venv python3-pip   # Debian/Ubuntu"
        echo "  sudo dnf install -y python3 python3-pip                # Fedora"
    fi
    exit 1
fi
ok "Python: $($PYTHON_BIN --version) ($(command -v "$PYTHON_BIN"))"

# ---------------------------------------------------------------------- #
# Ambil source: lokal (jika skrip dijalankan dari repo) atau clone
# ---------------------------------------------------------------------- #

SOURCE=""
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/../pyproject.toml" ]]; then
    SOURCE="$(cd "$SCRIPT_DIR/.." && pwd)"
    log "Memakai source lokal: $SOURCE"
elif [[ "$DEV_MODE" == "true" ]]; then
    die "Mode --dev butuh source lokal. Clone dulu repo-nya, lalu jalankan: bash install/install.sh --dev"
else
    mkdir -p "$INSTALL_HOME"
    if command -v git >/dev/null 2>&1; then
        if [[ -d "$SRC_DIR/.git" ]]; then
            log "Memperbarui source di $SRC_DIR"
            git -C "$SRC_DIR" fetch --depth 1 origin "$REPO_BRANCH" \
                && git -C "$SRC_DIR" reset --hard FETCH_HEAD \
                || die "Gagal memperbarui source. Hapus $SRC_DIR lalu ulangi."
        else
            rm -rf "$SRC_DIR"
            log "Clone $REPO_URL (branch $REPO_BRANCH)"
            git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR" \
                || die "Gagal clone repo. Periksa koneksi internet / nama branch."
        fi
    else
        warn "git tidak ditemukan - mengunduh arsip tar.gz dari GitHub."
        command -v curl >/dev/null 2>&1 || die "curl atau git diperlukan. Install salah satu dulu."
        command -v tar  >/dev/null 2>&1 || die "tar diperlukan."
        REPO_BASE="${REPO_URL%.git}"
        rm -rf "$SRC_DIR"; mkdir -p "$SRC_DIR"
        curl -fsSL "$REPO_BASE/archive/refs/heads/$REPO_BRANCH.tar.gz" \
            | tar -xz --strip-components=1 -C "$SRC_DIR" \
            || die "Gagal mengunduh arsip dari $REPO_BASE"
    fi
    [[ -f "$SRC_DIR/pyproject.toml" ]] || die "pyproject.toml tidak ada di $SRC_DIR - repo/branch salah?"
    SOURCE="$SRC_DIR"
    ok "Source siap: $SOURCE"
fi

# ---------------------------------------------------------------------- #
# Buat virtualenv
# ---------------------------------------------------------------------- #

make_venv() {
    rm -rf "$VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1
}

mkdir -p "$INSTALL_HOME"
log "Membuat virtualenv di $VENV_DIR"
if ! make_venv; then
    warn "Pembuatan venv gagal (paket python3-venv kemungkinan belum ada)."
    if command -v apt-get >/dev/null 2>&1; then
        PYVER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        SUDO=""
        if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
            command -v sudo >/dev/null 2>&1 && SUDO="sudo" \
                || die "Butuh root untuk install python3-venv. Jalankan: apt install python3-venv"
        fi
        log "Menginstall python3-venv via apt..."
        $SUDO apt-get update -qq || true
        $SUDO apt-get install -y -qq python3-venv "python${PYVER}-venv" 2>/dev/null \
            || $SUDO apt-get install -y -qq python3-venv \
            || die "Gagal install python3-venv."
        make_venv || die "Gagal membuat virtualenv setelah install python3-venv."
    else
        die "Gagal membuat virtualenv. Pastikan modul venv Python tersedia."
    fi
fi
ok "Virtualenv dibuat"

# ---------------------------------------------------------------------- #
# Install package di dalam venv
# ---------------------------------------------------------------------- #

log "Memperbarui pip di dalam venv..."
"$VENV_PY" -m pip install --quiet --upgrade pip setuptools wheel

log "Menginstall findref dan dependensinya..."
if [[ "$DEV_MODE" == "true" ]]; then
    "$VENV_PY" -m pip install --editable "$SOURCE" \
        || die "pip install gagal."
else
    "$VENV_PY" -m pip install "$SOURCE" \
        || die "pip install gagal."
fi
ok "Package ter-install"

# ---------------------------------------------------------------------- #
# Buat perintah global (symlink)
# ---------------------------------------------------------------------- #

mkdir -p "$BIN_DIR"
for name in findref find-refs; do
    target="$VENV_DIR/bin/$name"
    if [[ -x "$target" ]]; then
        ln -sf "$target" "$BIN_DIR/$name"
    fi
done
ok "Perintah dibuat di $BIN_DIR"

# ---------------------------------------------------------------------- #
# PATH
# ---------------------------------------------------------------------- #

PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
NEED_RELOAD=false

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    NEED_RELOAD=true
    if [[ "$MODIFY_PATH" == "true" ]]; then
        for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            # .bashrc selalu dibuat bila belum ada; rc lain hanya diubah bila sudah ada
            if [[ -f "$rc" || "$rc" == "$HOME/.bashrc" ]]; then
                if ! grep -qsF "# findref" "$rc"; then
                    printf '\n# findref\n%s\n' "$PATH_LINE" >> "$rc"
                    ok "PATH ditambahkan ke $rc"
                fi
            fi
        done
    else
        warn "$BIN_DIR belum ada di PATH. Tambahkan manual:"
        echo "  $PATH_LINE"
    fi
    export PATH="$BIN_DIR:$PATH"
fi

# ---------------------------------------------------------------------- #
# Verifikasi
# ---------------------------------------------------------------------- #

if "$BIN_DIR/findref" --version >/dev/null 2>&1; then
    ok "$("$BIN_DIR/findref" --version)"
else
    die "Instalasi selesai tetapi 'findref --version' gagal. Coba: $VENV_PY -m find_references_scopus --version"
fi

echo ""
log "Instalasi selesai!"
if [[ "$NEED_RELOAD" == "true" ]]; then
    echo -e "  Buka terminal baru atau jalankan: ${BOLD}source ~/.bashrc${NC}"
    echo ""
fi
echo -e "Langkah berikutnya:"
echo -e "  ${BOLD}findref setup${NC}     # Konfigurasi API key (interaktif)"
echo -e "  ${BOLD}findref doctor${NC}    # Diagnosa instalasi"
echo -e "  ${BOLD}findref guide${NC}     # Panduan penggunaan"
echo ""
echo -e "Perbarui nanti dengan menjalankan ulang perintah instalasi yang sama."
echo -e "Hapus dengan: ${BOLD}bash install.sh --uninstall${NC}"
echo ""

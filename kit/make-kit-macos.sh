#!/bin/bash
# Builds the macOS kit: the Arena (Arena.app) plus the toolchains teams need,
# in one folder that runs on any Apple Silicon Mac without installing
# anything: no Python, no JDK, no Xcode.
#
#     Arena-Kit-macOS/
#       Arena.app            open this
#       README.txt
#       README-protocol.md
#       templates/           a starter bot in Python, Java, C and C++
#       Terminal here.command a terminal with the tools on PATH
#       tools/python/        a relocatable CPython (python-build-standalone)
#       tools/jdk/           javac + java (Temurin)
#       tools/zig/           Zig, whose clang builds C and C++ with no Xcode
#       tools/bin/           gcc, g++, cc, c++: wrappers around it
#
# The macOS counterpart of make-kit.ps1. Run it from anywhere in the repo:
#
#     kit/make-kit-macos.sh [--branch ipd|rps] [--out DIR]
#
# The kit is for the game the branch plays (the current branch by default):
# rps for the practice kit. The Arena is built from that branch's committed
# files with the kit's own Python, so it carries nothing from this machine.
# Downloads are cached in kit/.cache-macos and checked: the JDK and Zig
# against their published checksums, Python against kit/hashes-macos.json
# (recorded on the first run; commit it).

set -euo pipefail

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
OUT="Arena-Kit-macOS"
while [ $# -gt 0 ]; do
    case "$1" in
        --branch) BRANCH="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "usage: $0 [--branch NAME] [--out DIR]" >&2; exit 2 ;;
    esac
done
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac

[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo "this builds the Apple Silicon kit, on an Apple Silicon Mac" >&2; exit 1; }

PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7%2B20241016-aarch64-apple-darwin-install_only.tar.gz"
JDK_API="https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse"
ZIG_VERSION="0.16.0"

CACHE="$ROOT/kit/.cache-macos"
HASHES="$ROOT/kit/hashes-macos.json"
mkdir -p "$CACHE"

say() { printf '%s\n' "$*"; }

# A cached download, checked against $3 (a published sha256) or, failing
# that, against the hash recorded for it in hashes-macos.json.
download() {
    local name="$1" url="$2" expected="${3:-}" file="$CACHE/$1"
    if [ ! -f "$file" ]; then
        say "  downloading $name …"
        curl -fL --retry 3 -o "$file.part" "$url"
        mv "$file.part" "$file"
    fi
    local sha
    sha=$(shasum -a 256 "$file" | cut -d' ' -f1)
    if [ -z "$expected" ] && [ -f "$HASHES" ]; then
        expected=$(plutil -extract "$name" raw -o - "$HASHES" 2>/dev/null || true)
    fi
    if [ -n "$expected" ] && [ "$expected" != "$sha" ]; then
        say "$name hash mismatch: expected $expected, got $sha. Delete $file and retry, or update the hash deliberately." >&2
        exit 1
    fi
    RECORD=""
    [ -z "$expected" ] && RECORD="$name $sha"
    DOWNLOADED="$file"
}

# Record a first-seen hash, with the kit's own Python (so no Python is needed
# on the machine building the kit).
record_hash() {
    [ -n "$1" ] || return 0
    set -- $1
    say "  recording hash for $1 ($2)"
    "$KITPY" - "$HASHES" "$1" "$2" <<'PY'
import json, os, sys
path, name, sha = sys.argv[1:]
data = json.load(open(path)) if os.path.exists(path) else {}
data[name] = sha
open(path, "w").write(json.dumps(data, indent=2) + "\n")
PY
}
json() { "$KITPY" -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1"; }

# ---------------------------------------------------------------- downloads

say "Arena kit for macOS, from the $BRANCH branch"
download python "$PYTHON_URL"
PYTHON_TGZ="$DOWNLOADED"; PYTHON_RECORD="$RECORD"

say "assembling $OUT"
rm -rf "$OUT"
TOOLS="$OUT/tools"
mkdir -p "$TOOLS/bin"
tar -xzf "$PYTHON_TGZ" -C "$TOOLS"                       # -> tools/python
KITPY="$TOOLS/python/bin/python3"
record_hash "$PYTHON_RECORD"

JDK_JSON=$(curl -fsL "$JDK_API")
JDK_URL=$(printf '%s' "$JDK_JSON" | json "d[0]['binary']['package']['link']")
JDK_SHA=$(printf '%s' "$JDK_JSON" | json "d[0]['binary']['package']['checksum']")
download jdk "$JDK_URL" "$JDK_SHA"
JDK_TGZ="$DOWNLOADED"

ZIG_JSON=$(curl -fsL https://ziglang.org/download/index.json)
ZIG_URL=$(printf '%s' "$ZIG_JSON" | json "d['$ZIG_VERSION']['aarch64-macos']['tarball']")
ZIG_SHA=$(printf '%s' "$ZIG_JSON" | json "d['$ZIG_VERSION']['aarch64-macos']['shasum']")
download zig "$ZIG_URL" "$ZIG_SHA"
ZIG_TXZ="$DOWNLOADED"

X=$(mktemp -d "$CACHE/x.XXXX")
tar -xzf "$JDK_TGZ" -C "$X"
mv "$X"/*/Contents/Home "$TOOLS/jdk"                      # the JDK proper, without its bundle wrapping
mkdir -p "$TOOLS/licenses"
[ -d "$TOOLS/jdk/legal" ] && cp -R "$TOOLS/jdk/legal" "$TOOLS/licenses/jdk-legal"
rm -rf "$X"; X=$(mktemp -d "$CACHE/x.XXXX")
tar -xJf "$ZIG_TXZ" -C "$X"
mv "$X"/zig-* "$TOOLS/zig"
rm -rf "$X"
cp "$TOOLS/zig/LICENSE" "$TOOLS/licenses/zig-LICENSE" 2>/dev/null || true
cp "$TOOLS/python/lib/python3.12/LICENSE.txt" "$TOOLS/licenses/python-LICENSE.txt" 2>/dev/null || true
for pair in "gcc cc" "cc cc" "g++ c++" "c++ c++"; do
    set -- $pair
    cat > "$TOOLS/bin/$1" <<EOF
#!/bin/sh
# $1, from the kit: Zig's clang. The explicit target makes Zig use its own
# macOS headers and libraries, so it never looks for Xcode.
exec "\$(cd "\$(dirname "\$0")/../zig" && pwd)/zig" $2 -target aarch64-macos "\$@"
EOF
    chmod +x "$TOOLS/bin/$1"
done
# Zig keeps a cache of what it has built; keep it out of the kit folder.
export ZIG_GLOBAL_CACHE_DIR="$CACHE/zig-cache"

# ------------------------------------------------- the Arena, from the branch

say "building the Arena ($BRANCH) with the kit's Python"
SRC="$CACHE/src"
rm -rf "$SRC"; mkdir -p "$SRC"
git -C "$ROOT" archive "$BRANCH" | tar -x -C "$SRC"
VENV="$CACHE/buildenv"
if [ ! -x "$VENV/bin/python" ]; then
    "$KITPY" -m venv "$VENV"
    "$VENV/bin/python" -m pip install -q "pyinstaller==6.*"
fi
# This Python links Tk into itself and finds Tk's files relative to itself, which a
# venv breaks; without these PyInstaller decides Tk is broken and leaves it out.
export TCL_LIBRARY="$TOOLS/python/lib/tcl8.6" TK_LIBRARY="$TOOLS/python/lib/tk8.6"
( cd "$SRC/arena" && "$VENV/bin/pyinstaller" --noconfirm --clean --log-level WARN --onefile --windowed \
      --name Arena --hidden-import sparring --hidden-import harness --hidden-import rules \
      --distpath "$CACHE/dist" --workpath "$CACHE/build" --specpath "$CACHE" arena.py )
cp -R "$CACHE/dist/Arena.app" "$OUT/Arena.app"
cp "$SRC/starter/README.md" "$OUT/README-protocol.md"
cp -R "$SRC/starter/templates" "$OUT/templates"
rm -rf "$OUT/templates"/*/versions

cat > "$OUT/README.txt" <<'EOF'
The Arena - everything you need, nothing to install (macOS, Apple Silicon)
=========================================================================

1. Open Arena.app. The first time, macOS may say it can't check who made it:
   right-click Arena.app, choose Open, then Open again.
2. Click "+ Add bot" and pick your bot's source file (templates/ has a
   starter in Python, Java, C and C++; copy one and edit choose()).
3. Pick your bot, open its Check tab and click Check; then Run tournament.

Python, Java, C and C++ all work straight from this folder: the Arena puts
tools/ on its own PATH. Nothing is installed, and you don't need Xcode.

Copied from a download rather than from a flash drive? macOS may then refuse
to run the tools inside. Once, in Terminal:
    xattr -dr com.apple.quarantine "path/to/this/folder"

Prefer a terminal? "Terminal here.command" opens one with python3, javac,
gcc and g++ ready.

The protocol your bot speaks is described in README-protocol.md.
Licences for the bundled tools are in tools/licenses/.
EOF

cat > "$OUT/Terminal here.command" <<'EOF'
#!/bin/bash
# A terminal with the kit's tools on PATH.
KIT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$KIT/tools/bin:$KIT/tools/python/bin:$KIT/tools/jdk/bin:$PATH"
export JAVA_HOME="$KIT/tools/jdk"
cd "$KIT"
echo "python3, javac, gcc and g++ are ready in this window."
exec "$SHELL" -l
EOF
chmod +x "$OUT/Terminal here.command"

# -------------------------------------------------------------------- check

say "checking the kit"
# Only the kit's tools and the system's basics, as on a Mac without Xcode.
KITPATH="$TOOLS/bin:$TOOLS/python/bin:$TOOLS/jdk/bin:/usr/bin:/bin"
run() { env -i HOME="$HOME" PATH="$KITPATH" JAVA_HOME="$TOOLS/jdk" ZIG_GLOBAL_CACHE_DIR="$ZIG_GLOBAL_CACHE_DIR" "$@"; }
say "  $(run python3 -V)  ·  $(run javac -version 2>&1)  ·  zig $(run "$TOOLS/zig/zig" version)"

MOVES=$(run python3 -c "import sys; sys.path.insert(0, sys.argv[1]); from rules import GAME; print(''.join(GAME.moves))" "$SRC/arena")
SESSION=$(printf 'RESET\nROUND - -\nROUND %s %s\nEND\n' "${MOVES:0:1}" "${MOVES: -1}")
T=$(mktemp -d "$CACHE/templates.XXXX")
cp -R "$OUT/templates/." "$T/"
# Built as the Arena builds them. The first C++ build compiles Zig's own libc++,
# with a lot of harmless warnings: show the output only if a build fails.
build_quietly() {
    local dir="$1"; shift
    ( cd "$T/$dir" && run "$@" ) > "$CACHE/build-$dir.log" 2>&1 || {
        tail -30 "$CACHE/build-$dir.log"; say "the $dir template did not build" >&2; exit 1; }
}
build_quietly java javac MyBot.java
build_quietly c gcc -O2 -o my_bot my_bot.c -lm
build_quietly cpp g++ -O2 -std=c++17 -o my_bot my_bot.cpp
for lang in python java c cpp; do
    case $lang in
        python) cmd=(python3 my_bot.py) ;;
        java) cmd=(java -cp . MyBot) ;;
        *) cmd=(./my_bot) ;;
    esac
    reply=$(cd "$T/$lang" && printf '%s' "$SESSION" | run "${cmd[@]}" | tr -d '\n')
    [[ "$reply" =~ ^[$MOVES]+$ ]] || { say "the $lang template did not play: '$reply'" >&2; exit 1; }
    say "  $lang template replied: $(printf '%s' "$reply" | sed 's/./& /g')"
done
rm -rf "$T"

# The app must carry nothing from this machine: no /nix/store paths in any
# library it bundles.
"$VENV/bin/python" - "$CACHE/dist/Arena" <<'PY'
import subprocess, sys, tempfile, os
from PyInstaller.archive.readers import CArchiveReader
car = CArchiveReader(sys.argv[1])
bad, checked = [], 0
with tempfile.TemporaryDirectory() as tmp:
    for name, entry in car.toc.items():
        if entry[-1] not in "bn":            # binaries and extensions
            continue
        path = os.path.join(tmp, os.path.basename(name))
        open(path, "wb").write(car.extract(name))
        out = subprocess.run(["otool", "-L", path], capture_output=True, text=True).stdout
        checked += 1
        bad += [f"{name}: {line.strip()}" for line in out.splitlines()[1:]
                if "/nix/" in line or "/opt/homebrew" in line or "/usr/local/" in line]
tk = [n for n in car.toc if n.startswith(("_tcl_data", "_tk_data"))]
if not any(n.startswith("_tcl_data") for n in tk) or not any(n.startswith("_tk_data") for n in tk):
    bad.append("Tcl/Tk's files are not in the bundle: the Arena could not open a window")
print(f"  {checked} bundled libraries, none tied to this machine; Tcl/Tk bundled ({len(tk)} files)"
      if not bad else "\n".join(bad))
sys.exit(1 if bad else 0)
PY

REPORT="$CACHE/selftest.txt"
rm -f "$REPORT"
run "$OUT/Arena.app/Contents/MacOS/Arena" --selftest "$REPORT" &
PID=$!
for _ in $(seq 240); do kill -0 $PID 2>/dev/null || break; sleep 1; done
if kill -0 $PID 2>/dev/null; then kill -9 $PID; say "the Arena's self-test did not finish within 4 minutes" >&2; exit 1; fi
wait $PID || { cat "$REPORT" 2>/dev/null; say "the Arena's self-test failed" >&2; exit 1; }
say "  Arena self-test: $(tail -1 "$REPORT" | sed 's/^\[[^]]*\] //') ($(grep -o 'python: [^ ]*' "$REPORT" | head -1))"

# ---------------------------------------------------------------------- zip

ZIP="$OUT.zip"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$OUT" "$ZIP"
say "kit ready: $OUT ($(du -sh "$OUT" | cut -f1)), zipped as $(basename "$ZIP") ($(du -sh "$ZIP" | cut -f1))"

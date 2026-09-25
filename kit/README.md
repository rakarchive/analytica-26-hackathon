# The flash-drive kit

One folder that gives a Windows machine a working bot setup: the Arena plus
Python, a JDK, and gcc and g++. Nothing is installed, no admin rights are needed, and
nothing on the machine is changed.

## Getting it

Every release builds it: the build workflow runs this script on its Windows
runner and attaches `Arena-Kit.zip` to the release, built on the release's
branch (the practice kit on `rps`, the event kit on `ipd`). Unzip it onto the
flash drives.

## Building it by hand

On a Windows machine with internet, once:

```powershell
pwsh -File make-kit.ps1 -Arena ..\arena\dist\Arena.exe
```

`Arena.exe` comes from the build workflow (`.github/workflows/build-arena.yml`)
or from PyInstaller. Useful switches:

| Switch | What it does |
|---|---|
| `-TrimJdk` | jlink a smaller JDK that still has `javac` (~80 MB instead of ~300 MB) |
| `-SkipMingw` | leave C and C++ out |
| `-CheckOnly` | check the downloads are reachable, build nothing |
| `-Out <dir>` | where to assemble (default `Arena-Kit`) |

Downloads are cached in `.cache`; their hashes go into `hashes.json`, which is
recorded on the first run and verified afterwards. Commit `hashes.json` so
every kit is built from the same bytes.

The script finishes by testing the kit: it builds and runs every template
(Python, Java, C, C++) with the bundled tools over the real protocol, and
runs the Arena's self-test.

## What teams get

Copy the assembled folder to a flash drive as it is. Teams copy it to the
machine (or run it from the drive), double-click `Arena.exe`, and add their
bot. The Arena puts `tools\` on its own PATH, so Java and C++ compile with no
installation. Python bots work even if `tools\python` is missing, because the
Arena runs them with the interpreter inside the exe.

Windows will warn that the app is unsigned: *More info → Run anyway*.

## The macOS kit

For Apple Silicon Macs, `make-kit-macos.sh` builds the same kit: `Arena.app`
plus a relocatable Python (python-build-standalone), Temurin's JDK, and Zig,
whose clang compiles C and C++ behind `gcc` and `g++` wrappers without Xcode.
Run it on a Mac with internet:

```bash
kit/make-kit-macos.sh --branch rps     # the practice kit; ipd for the event
```

It builds the Arena from the branch with the kit's own Python, so the app
carries nothing from the machine that built it, then checks the kit: every
template built and played with only the kit's tools, no bundled library tied
to the build machine, Tcl/Tk bundled, and the Arena's self-test. The result is
`Arena-Kit-macOS/` and `Arena-Kit-macOS.zip` (about 340 MB). Downloads are
cached in `kit/.cache-macos` and checked: the JDK and Zig against their
published checksums, Python against `hashes-macos.json`.

Copy it to the flash drives as a folder. macOS marks files that came from a
download as quarantined and then refuses to run the tools inside; files
copied from a drive aren't marked. The kit's README.txt says how to clear the
mark if someone downloads it instead.

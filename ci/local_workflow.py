"""The GitHub workflow (.github/workflows/build-arena.yml), run locally.

The real workflow runs on a Windows runner, which cannot be reproduced
here, so this does the same steps natively, in the same order:

  1. which game this branch plays (arena/rules.py)
  2. for anything but the event game, check nothing names the real game
  3. build every template the way the Arena builds them, and play it
  4. build the Arena with PyInstaller, with the workflow's options
  5. self-test the packaged app (and, extra here, again with no Python on
     the PATH, so bots run on the app's own interpreter)
  6. assemble the download: the app, README.md and the templates, zipped

It works on a snapshot of one commit, extracted under .ci/work, so the
working tree can change while it runs. Runs take turns. The log, the
status, the app and Arena.zip end up in .ci/runs/<branch>/.

    python ci/local_workflow.py [--commit REV] [--branch NAME] [--notify]

The post-commit hook runs it in the background after every commit:

    #!/bin/sh
    repo=$(git rev-parse --show-toplevel)
    py="$repo/.ci/python-tk/bin/python3"; [ -x "$py" ] || py=python3
    nohup "$py" "$repo/ci/local_workflow.py" --commit "$(git rev-parse HEAD)" \\
        --branch "$(git rev-parse --abbrev-ref HEAD)" --notify >/dev/null 2>&1 &

It needs a Python with tkinter (the one it runs on, or --python), a JDK,
and gcc/g++. A .ci/jdk folder is put on the PATH if there is one.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI = os.path.join(ROOT, ".ci")
WINDOWS = sys.platform == "win32"
EXE = ".exe" if WINDOWS else ""

# The same list as the workflow's "must not give the real game away" step.
LEAK_WORDS = ["prisoner", "cooperat", "defect", r"tit.for.tat", "titfortat", "pavlov", "grudge",
              r"\bipd\b"]


class Failed(Exception):
    pass


class Run:
    def __init__(self, commit, branch, python):
        self.commit, self.branch, self.python = commit, branch, python
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", branch)
        self.work = os.path.join(CI, "work", safe)
        self.out = os.path.join(CI, "runs", safe)
        os.makedirs(self.out, exist_ok=True)
        self.log_file = open(os.path.join(self.out, "log.txt"), "w", buffering=1)
        self.t0 = time.time()
        self.env = dict(os.environ)
        jdk = os.path.join(CI, "jdk", "bin")
        if os.path.isdir(jdk):
            self.env["PATH"] = jdk + os.pathsep + self.env.get("PATH", "")

    def log(self, text=""):
        for line in str(text).rstrip("\n").split("\n"):
            self.log_file.write(f"[{time.time() - self.t0:6.1f}s] {line}\n")

    def step(self, name):
        self.log()
        self.log(f"== {name}")

    def sh(self, cmd, cwd, timeout=600, env=None, input=None, check=True):
        r = subprocess.run(cmd, cwd=cwd, env=env or self.env, input=input, capture_output=True,
                           text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip()
        if check and r.returncode != 0:
            self.log(out)
            raise Failed(f"{os.path.basename(cmd[0])} exited {r.returncode}")
        return r

    # ---------------- the steps ----------------

    def snapshot(self):
        self.step(f"snapshot of {self.commit[:10]} ({self.branch})")
        shutil.rmtree(self.work, ignore_errors=True)
        os.makedirs(self.work)
        archive = subprocess.run(["git", "archive", "--format=tar", self.commit], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        with tempfile.TemporaryFile() as f:
            f.write(archive)
            f.seek(0)
            with tarfile.open(fileobj=f) as tar:
                try:
                    tar.extractall(self.work, filter="data")
                except TypeError:            # Python before 3.12
                    tar.extractall(self.work)
        self.arena = os.path.join(self.work, "arena")
        subject = subprocess.run(["git", "log", "-1", "--format=%s", self.commit], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip()
        self.log(subject)

    def which_game(self):
        self.step("Which game this is")
        r = self.sh([self.python, "-c", "from rules import GAME; print(GAME.key, ''.join(GAME.moves))"],
                    cwd=self.arena)
        self.key, self.moves = r.stdout.split()
        self.log(f"building the Arena for: {self.key} (moves {self.moves})")

    def leak_scan(self):
        self.step("A practice build must not give the real game away")
        if self.key == "ipd":
            self.log("skipped: this is the event game")
            return
        files = glob.glob(os.path.join(self.arena, "*.py")) + [
            p for p in glob.glob(os.path.join(self.work, "starter", "**", "*"), recursive=True)
            if os.path.isfile(p)]
        leaks = []
        for path in files:
            with open(path, errors="replace") as f:
                for k, line in enumerate(f, 1):
                    for w in LEAK_WORDS:
                        if re.search(w, line, flags=re.I):
                            leaks.append(f"{os.path.relpath(path, self.work)}:{k}: {w}")
        if leaks:
            self.log("\n".join(leaks))
            raise Failed("the practice build names the real game")
        self.log("nothing in the practice build names the real game")

    def templates(self):
        self.step("Every template builds and plays")
        session = f"RESET\nROUND - -\nROUND {self.moves[0]} {self.moves[-1]}\nEND\n"
        work = tempfile.mkdtemp(prefix="templates-", dir=CI)
        try:
            shutil.copytree(os.path.join(self.work, "starter", "templates"), work, dirs_exist_ok=True)
            static = ["-static"] if WINDOWS else []
            self.sh(["javac", "MyBot.java"], cwd=os.path.join(work, "java"))
            self.sh(["gcc", "-O2", *static, "-o", "my_bot" + EXE, "my_bot.c", "-lm"],
                    cwd=os.path.join(work, "c"))
            self.sh(["g++", "-O2", "-std=c++17", *static, "-o", "my_bot" + EXE, "my_bot.cpp"],
                    cwd=os.path.join(work, "cpp"))
            runs = [("Python", [self.python, "my_bot.py"], "python"),
                    ("Java", ["java", "-cp", ".", "MyBot"], "java"),
                    ("C", [os.path.join(work, "c", "my_bot" + EXE)], "c"),
                    ("C++", [os.path.join(work, "cpp", "my_bot" + EXE)], "cpp")]
            for name, cmd, folder in runs:
                r = self.sh(cmd, cwd=os.path.join(work, folder), input=session, timeout=60)
                reply = r.stdout.split()
                if not reply or not re.fullmatch(f"[{self.moves}]+", "".join(reply)):
                    raise Failed(f"the {name} template did not play: {reply!r}")
                self.log(f"{name} replied: {' '.join(reply)}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def build(self):
        self.step("Build Arena")
        venv = os.path.join(CI, "venv")
        vpy = os.path.join(venv, "Scripts" if WINDOWS else "bin", "python" + EXE)
        if not os.path.exists(vpy):
            self.log("making the build environment (once)")
            self.sh([self.python, "-m", "venv", "--system-site-packages", venv], cwd=ROOT)
            self.sh([vpy, "-m", "pip", "install", "-q", "pyinstaller==6.*"], cwd=ROOT, timeout=900)
        env = dict(self.env)
        env.update(self.tk_libraries(vpy))
        self.sh([vpy, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN", "--onefile", "--windowed",
                 "--name", "Arena", "--hidden-import", "sparring", "--hidden-import", "harness",
                 "--hidden-import", "rules", "arena.py"], cwd=self.arena, env=env, timeout=1200)
        self.exe = os.path.join(self.arena, "dist", "Arena" + EXE)
        if not os.path.isfile(self.exe):
            raise Failed("PyInstaller made no Arena" + EXE)
        self.log(f"built {os.path.relpath(self.exe, self.work)} "
                 f"({os.path.getsize(self.exe) / 1e6:.1f} MB)")

    def tk_libraries(self, vpy):
        """PyInstaller looks for Tk's script library next to Tcl's. Some
        installs (Nix) keep them apart: give it a merged copy."""
        r = self.sh([vpy, "-c", "import tkinter; t = tkinter.Tk(); t.withdraw(); "
                                "print(t.eval('info library')); print(t.eval('set tk_library'))"],
                    cwd=ROOT, check=False)
        lines = r.stdout.split("\n")
        if r.returncode or len(lines) < 2:
            return {}
        tcl, tk = lines[0].strip(), lines[1].strip()
        if os.path.dirname(tcl) == os.path.dirname(tk):
            return {}
        merged = os.path.join(CI, "tcltk")
        for src in (tcl, tk):
            dst = os.path.join(merged, os.path.basename(src))
            if not os.path.isdir(dst):
                shutil.copytree(src, dst)
        return {"TCL_LIBRARY": os.path.join(merged, os.path.basename(tcl)),
                "TK_LIBRARY": os.path.join(merged, os.path.basename(tk))}

    def self_test(self, label, env):
        self.step(label)
        report = os.path.join(self.out, "selftest.txt")
        if os.path.exists(report):
            os.remove(report)
        proc = subprocess.Popen([self.exe, "--selftest", report], cwd=self.arena, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=240)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.log(open(report).read() if os.path.exists(report) else "(no report was written)")
            raise Failed("the self-test did not finish within 4 minutes")
        self.log(open(report).read() if os.path.exists(report) else "(no report was written)")
        left = subprocess.run(["pgrep", "-fl", self.exe], capture_output=True, text=True).stdout.strip() \
            if not WINDOWS else ""
        if left:
            self.log("processes still running after the self-test:\n" + left)
        if proc.returncode != 0:
            raise Failed(f"the self-test failed (exit {proc.returncode})")
        if f"game: {self.key}" not in open(report).read():
            raise Failed(f"the app is not playing {self.key}")

    def assemble(self):
        self.step("Assemble the download")
        package = os.path.join(self.out, "package")
        shutil.rmtree(package, ignore_errors=True)
        os.makedirs(package)
        shutil.copy2(self.exe, package)
        shutil.copy2(os.path.join(self.work, "starter", "README.md"), package)
        shutil.copytree(os.path.join(self.work, "starter", "templates"), os.path.join(package, "templates"))
        zipped = shutil.make_archive(os.path.join(self.out, "Arena"), "zip", package)
        self.log(f"{os.path.relpath(zipped, ROOT)} ({os.path.getsize(zipped) / 1e6:.1f} MB)")

    def go(self):
        self.snapshot()
        self.which_game()
        self.leak_scan()
        self.templates()
        self.build()
        self.self_test("Self-test the packaged app", self.env)
        no_python = dict(self.env)
        no_python["PATH"] = os.pathsep.join(p for p in self.env["PATH"].split(os.pathsep)
                                            if not glob.glob(os.path.join(p, "python*"))
                                            and not glob.glob(os.path.join(p, "py" + EXE)))
        self.self_test("Self-test with no Python on the PATH (bots run on the app's own Python)",
                       no_python)
        self.assemble()


def take_turn():
    """One run at a time: a lock folder, waited for, and taken over if its
    owner has gone."""
    lock = os.path.join(CI, "lock")
    os.makedirs(CI, exist_ok=True)
    while True:
        try:
            os.mkdir(lock)
            with open(os.path.join(lock, "pid"), "w") as f:
                f.write(str(os.getpid()))
            return lock
        except FileExistsError:
            try:
                pid = int(open(os.path.join(lock, "pid")).read())
                os.kill(pid, 0)
            except (OSError, ValueError):
                shutil.rmtree(lock, ignore_errors=True)   # its owner is gone
                continue
            time.sleep(2)


def notify(title, text):
    if sys.platform == "darwin":
        script = f'display notification "{text}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--branch")
    ap.add_argument("--python", default=sys.executable, help="a Python with tkinter")
    ap.add_argument("--notify", action="store_true", help="a desktop notification when done")
    args = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", args.commit], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    branch = args.branch or subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                                           capture_output=True, text=True).stdout.strip()
    lock = take_turn()
    run = Run(commit, branch, args.python)
    status = os.path.join(run.out, "status")
    with open(status, "w") as f:
        f.write(f"RUNNING {commit[:10]} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    ok = False
    try:
        run.go()
        ok = True
    except Failed as e:
        run.log(f"FAILED: {e}")
    except Exception as e:  # a bug in this script, or a tool missing
        run.log(f"FAILED: {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(lock, ignore_errors=True)
    secs = time.time() - run.t0
    run.log()
    run.log(("PASS" if ok else "FAIL") + f" in {secs:.0f}s")
    with open(status, "w") as f:
        f.write(f"{'PASS' if ok else 'FAIL'} {commit[:10]} {time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({secs:.0f}s)\n")
    if args.notify:
        notify(f"Local workflow: {branch} {'passed' if ok else 'FAILED'}",
               f"{commit[:8]} in {secs:.0f}s. Log: .ci/runs/{branch}/log.txt")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_TOKEN = "<ROOT>"
GIT_IDENTITY = ("-c", "user.name=pin", "-c", "user.email=pin@example.invalid", "-c", "commit.gpgsign=false")
COMMENT_DEBT = "quality_gates.comment_debt"
CC_CHECK = "quality_gates.quality_check"
CRAP = "quality_gates.crap"
OLD = 1_000_000_000
NEW = 2_000_000_000
UNRESOLVABLE = (
    "import os, runpy, sys\n"
    "from quality_gates import ratchet, real_path\n"
    "os.path.lexists('loop1') or (os.symlink('loop2', 'loop1'), os.symlink('loop1', 'loop2'))\n"
    "ratchet.real_path = lambda name: real_path.real_path('loop1')\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_module(sys.argv[0], run_name='__main__', alter_sys=True)\n"
)


class Ran:
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err

    def triple(self):
        return (self.code, self.out, self.err)


class Project:
    def __init__(self, files=None, repo=True, commit=True):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="gate-pin-")))
        self.repo = repo
        if repo:
            self.git("init", "-q", ".")
        for name, text in (files or {}).items():
            self.write(name, text)
        if repo and commit and files:
            self.commit(*files)

    def git(self, *args):
        subprocess.run(["git", *GIT_IDENTITY, *args], cwd=self.root, check=True, capture_output=True)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, *names):
        self.git("add", *names)
        self.git("commit", "-q", "-m", "fixture")

    def untrack(self, name):
        self.git("rm", "-q", "--cached", name)
        self.git("commit", "-q", "-m", "untrack")

    def date(self, name, stamp):
        os.utime(self.root / name, (stamp, stamp))

    def read(self, name):
        return (self.root / name).read_bytes()

    def exists(self, name):
        return (self.root / name).exists()

    def normalise(self, text):
        forms = {str(self.root), str(self.root.resolve()), os.path.realpath(self.root)}
        for form in sorted(forms, key=len, reverse=True):
            text = text.replace(form, ROOT_TOKEN)
        return text

    def run(self, module, *args):
        return self.ran([sys.executable, "-m", module, *args])

    def run_unresolvable(self, module, *args):
        return self.ran([sys.executable, "-c", UNRESOLVABLE, module, *args])

    def ran(self, command):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", NO_COLOR="1")
        done = subprocess.run(command, cwd=self.root, capture_output=True, env=env)
        return Ran(
            done.returncode,
            self.normalise(done.stdout.decode("utf-8")),
            self.normalise(done.stderr.decode("utf-8")),
        )

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def project(test, files=None, **kwargs):
    made = Project(files, **kwargs)
    test.addCleanup(made.cleanup)
    return made

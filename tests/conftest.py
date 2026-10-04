import subprocess
from types import SimpleNamespace

import pytest
from loguru import logger

import moccarun

SLURM = """#!/bin/bash -l
## job name
#SBATCH -J MOCCA_slurm_job
#SBATCH --mem-per-cpu=2999MB
#SBATCH --time=336:00:00
## partition (queue) to use
#SBATCH -p long
#SBATCH --mail-type=ALL
##SBATCH --mail-user=somebody@example.org

ulimit -s 5000000
./mocca > zzz
exit 0;
"""

INI = """[StarCluster]
# comment about n
#    - default value: 1
n = 1000, 500  # trailing comment
# fracb = 0.1
fracb = 0.95

[Technical]
runmaxcpu = 0
"""


def git(cwd, *args):
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false"]
    p = subprocess.run([*cmd, *args], cwd=cwd, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def make_mocca_repo(root, remote="git@example.org:mocca/mocca.git"):
    """A git repo with a MOCCA-like src/ (the files MOCCA identification needs); returns src"""
    src = root / "src"
    (src / "MOCCA").mkdir(parents=True)
    (src / "makefile").write_text("default: mocca\n\nmocca: headers common\n\t$(FC) -o mocca\n")
    for f in ("montcarl.f", "input.f", "version.f", "params.h"):
        (src / "MOCCA" / f).write_text("")
    (src / "mocca-default-1pop.ini").write_text(INI)
    (src / "mocca-default-2pop.ini").write_text(INI)
    (src / "mocca.slurm").write_text(SLURM)
    for d in ("bse", "fewbody", "iniparser", "marsene"):
        (src / d).mkdir()
        (src / d / "x.c").write_text("")
    (src / "mocca").write_text("binary")  # built binary, untracked in reality; harmless here
    git(root, "init", "-q")
    if remote:
        git(root, "remote", "add", "origin", remote)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "root")
    return src


@pytest.fixture
def project(tmp_path):
    """<tmp>/proj (git repo) containing <tmp>/proj/mocca (its own MOCCA-like git repo)"""
    proj = tmp_path / "proj"
    proj.mkdir()
    git(proj, "init", "-q")
    src = make_mocca_repo(proj / "mocca")
    return SimpleNamespace(root=proj, src=src, runs=proj / "runs")


@pytest.fixture
def log(monkeypatch):
    """(level, message) of everything logged at INFO and above (the default level)"""
    records = []
    # main() reconfigures loguru; keep this sink
    monkeypatch.setattr(moccarun, "setup_logging", lambda level="INFO": None)
    hid = logger.add(lambda m: records.append((m.record["level"].name, m.record["message"])), level="INFO")
    yield records
    try:
        logger.remove(hid)
    except ValueError:
        pass


def has(log, level, text):
    """was something logged at `level` containing `text`?"""
    return any(lvl == level and text in msg for lvl, msg in log)

#!/usr/bin/env python3

__VERSION__ = "2610061623"

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from argparse import ArgumentParser, ArgumentTypeError
from functools import cache
from itertools import product
from pathlib import Path

from loguru import logger

# Name of the MOCCA git repository (last component of a remote URL, e.g. .../mocca/mocca.git)
MOCCA_REPO_NAME = "mocca"

# Paths (relative to src/) that must be tracked by git in the MOCCA repository.
# Together with the repository name they identify a MOCCA checkout: the files
# alone (e.g. a mocca.slurm) can exist anywhere.
MOCCA_SRC_TRACKED = (
    "makefile",
    "MOCCA/montcarl.f",
    "MOCCA/input.f",
    "MOCCA/version.f",
    "MOCCA/params.h",
    "mocca-default-1pop.ini",
    "mocca-default-2pop.ini",
    "mocca.slurm",
    "bse",
    "fewbody",
    "iniparser",
    "marsene",
)

# Default simulation inputs: name in simulation dir -> name in MOCCA src/
DEFAULT_INPUTS = {"mocca.ini": "mocca-default-2pop.ini", "mocca.slurm": "mocca.slurm"}

MOCCA_SIZES = {"small", "large"}
MOCCA_MAKE_OPTS = MOCCA_SIZES | {"clean"}
CLEAN_MODES = {
    "all": ["mocca.ini", "mocca.slurm"],
    "outputs": ["mocca", "mocca.ini", "mocca.slurm", "binary_nbody.dat", "single_nbody.dat"],
}

# partition -> (--time, --mem-per-cpu, hours)
PARTITIONS = {
    "short": ("36:00:00", "2999MB", 36),
    "long": ("336:00:00", "2999MB", 336),
    "bigmem": ("168:00:00", "5999MB", 168),
}
# fraction of the partition's time limit (in minutes) at which MOCCA stops gently (for restarts)
RUNMAXCPU_FRAC = 0.9

# queue listing: only the current user's jobs, with a wide job-name column (%.48j)
SQUEUE_FORMAT = "%.8i %.9P %.48j %.12u %.8T %.12M %.12l %.6D %R"
# allocation requested by --srun: nodes, job name (-J), resources, node (-w), interactive bash
SRUN_NODES = ["-N", "1"]
SRUN_RES = ["--mem-per-cpu=8GB", "-p", "bigmem"]
SRUN_SHELL = ["--pty", "bash"]

# params.h limits: size -> (NMAX, NBMAX3, NSUPZO)
PARAMS_H_SIZES = {"small": (2200000, 2200000, 400), "large": (5200000, 5200000, 600)}

SOURCE_SUFFIXES = {".f", ".f90", ".f95", ".f03", ".f08", ".h"}

# argparse dest -> option name, for the dests argparse renames
OPTION_NAMES = {"ref_dir": "from", "run_sim": "run", "keep_mocca_binary": "keep-mocca-binary"}

# options --srun (an interactive shell) refuses to be combined with
SRUN_EXCLUSIVE = (
    "grep",
    "make",
    "clean",
    "grid",
    "moccaini",
    "mocca_src",
    "mocca_binary",
    "ref_dir",
    "keep_mocca_binary",
    "partition",
    "user_email",
    "no_slurm",
    "run_sim",
    "wait",
    "escape_bin_restart",
    "squeue",
)

# options ignored when --squeue is all that is asked for (no simulation to prepare)
SQUEUE_IGNORED = (
    "mocca_src",
    "mocca_binary",
    "ref_dir",
    "keep_mocca_binary",
    "moccaini",
    "partition",
    "user_email",
    "no_slurm",
    "wait",
    "escape_bin_restart",
)


class MoccaError(ValueError):
    """User-facing error: reported by main() without a traceback."""


def fix_path(path):
    """ensure that the path is Path() class and is absolute"""

    return Path(path).expanduser().absolute()


def run(cmd, **kwargs):
    """Run subprocess command

    A `str` command is run through the shell, a list is run directly.
    capture_output=True if not specified in kwargs.

    Args
        cmd (str | list): command to run
        **kwargs : passed to subprocess.run()
    Returns
        subprocess.CompletedProcess
    """
    kwargs.setdefault("shell", isinstance(cmd, str))
    kwargs.setdefault("capture_output", True)

    logger.debug(f"run {cmd=} {kwargs=}")
    return subprocess.run(cmd, **kwargs)


def git(*args, cwd) -> str | None:
    """stdout of a git command run in `cwd`, None on failure"""
    p = run(["git", "-C", str(cwd), *args])
    return p.stdout.decode().strip() if p.returncode == 0 else None


def git_user_email() -> str | None:
    try:
        p = run(["git", "config", "--get", "user.email"])
    except OSError:
        return None
    return p.stdout.decode().strip() or None if p.returncode == 0 else None


def get_user_email(cli_email: str | None = None) -> str:
    """Get user email for SLURM notifications.

    Priority: CLI arg > MOCCARUN_EMAIL env > git config user.email > EMAIL env
    """
    if cli_email:
        logger.info(f"email for SLURM notifications: {cli_email} (--user-email)")
        return cli_email

    if env_email := os.environ.get("MOCCARUN_EMAIL"):
        logger.info(f"email for SLURM notifications: {env_email} (MOCCARUN_EMAIL)")
        return env_email

    if email := git_user_email():
        logger.info(f"email for SLURM notifications: {email} (git config user.email)")
        return email
    logger.warning("no email in git config (user.email), trying the EMAIL env var")

    if system_email := os.environ.get("EMAIL"):
        logger.info(f"email for SLURM notifications: {system_email} (EMAIL)")
        return system_email

    raise MoccaError(
        "No email provided. Set --user-email, MOCCARUN_EMAIL env var, "
        "configure git (git config --global user.email), or set EMAIL env var."
    )


def clean_dir(path, keep=None):
    """Cleans the target directory from all files except those specified in `keep`"""

    path = fix_path(path)
    keep = keep or []

    doomed = sorted(item for item in path.iterdir() if item.name not in keep)
    logger.warning(f"cleaning {path}: removing {len(doomed)} item(s), keeping {keep}")
    for item in doomed:
        logger.debug(f"removing {item}")
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()


def remote_repo_names(repo) -> set[str]:
    """Repository names from the URLs of all git remotes (".../mocca/mocca.git" -> "mocca")"""
    out = git("config", "--get-regexp", r"^remote\..*\.url$", cwd=repo) or ""
    urls = (line.split(maxsplit=1)[1] for line in out.splitlines() if " " in line)
    return {re.split(r"[/:]", u.rstrip("/").removesuffix(".git"))[-1] for u in urls}


def validate_mocca_src(src) -> Path:
    """Verify that `src` is the src/ directory of the MOCCA git repository.

    Checks, in order:
    - the parent of `src` is the root of its own git repository (not e.g. an
      uninitialized submodule or a plain subdirectory of another repository);
    - that repository is named `MOCCA_REPO_NAME` on a git remote;
    - MOCCA-specific files (`MOCCA_SRC_TRACKED`) are tracked by git in `src`, and
      the makefile has the `mocca` target.

    Returns:
        the validated src path

    Raises:
        MoccaError: if any check fails
    """
    src = fix_path(src)
    repo = src.parent

    if not src.is_dir():
        raise MoccaError(f"not a directory: {src}")

    toplevel = git("rev-parse", "--show-toplevel", cwd=repo)
    if toplevel is None or Path(toplevel).resolve() != repo.resolve():
        raise MoccaError(
            f"{repo} is not a git repository root "
            "(uninitialized submodule? try: git submodule update --init)"
        )

    if MOCCA_REPO_NAME not in (names := remote_repo_names(repo)):
        raise MoccaError(
            f"{repo} is not the MOCCA repository: no git remote named "
            f"'{MOCCA_REPO_NAME}' (remote repository names: {sorted(names) or 'none'})"
        )

    tracked = (git("ls-files", "--", *MOCCA_SRC_TRACKED, cwd=src) or "").splitlines()
    missing = [
        f for f in MOCCA_SRC_TRACKED if not any(t == f or t.startswith(f + "/") for t in tracked)
    ]
    if missing:
        raise MoccaError(f"{src} is not MOCCA's src directory: not tracked by git: {missing}")

    if not re.search(r"^mocca\s*:", (src / "makefile").read_text(errors="replace"), re.M):
        raise MoccaError(f"{src}/makefile has no 'mocca' target")

    for f in DEFAULT_INPUTS.values():  # tracked, but may be deleted in the working tree
        if not (src / f).is_file():
            raise MoccaError(f"{src / f} not found")

    return src


def find_mocca_src_path(path=None) -> Path:
    """Find the MOCCA src/ directory: <git-root>/mocca/src, else <git-root>/src

    <git-root>/mocca/src is for a project containing MOCCA (e.g. as a submodule) and
    takes precedence; <git-root>/src is for MOCCA's own repository.
    The git root is that of `path` (default: current directory); `path` may not exist yet.

    Raises:
        MoccaError: if not in a git repository or no candidate is MOCCA's src
    """
    start = fix_path(path or Path.cwd())
    start = next(p for p in (start, *start.parents) if p.is_dir())

    root = git("rev-parse", "--show-toplevel", cwd=start)
    if root is None:
        raise MoccaError(f"{start} is not in a git repository; use --mocca-src")

    errors = []
    for candidate in (Path(root) / "mocca" / "src", Path(root) / "src"):
        try:
            return validate_mocca_src(candidate)
        except MoccaError as e:
            errors.append(f"{candidate}: {e}")
    raise MoccaError("MOCCA src not found:\n  " + "\n  ".join(errors))


def resolve_mocca_src(explicit=None, path=None) -> Path:
    """`--mocca-src` if given, otherwise <git-root>/mocca/src; always validated"""
    return validate_mocca_src(explicit) if explicit else find_mocca_src_path(path)


def resolve_mocca_binary(binary: Path) -> Path:
    """`--mocca-binary` may be the binary itself or a directory containing `mocca`"""
    binary = fix_path(binary)
    if binary.is_dir():
        binary /= "mocca"
    if not binary.is_file():
        raise MoccaError(f"mocca binary not found: {binary}")
    return binary


def set_moccaini(path, **kwargs):
    """make changes to mocca.ini file, keeping all comments

    Args:
        path (Path | str): path to mocca.ini file
        kwargs: key and values to update

    Raises:
        MoccaError: if a key is not set (or only commented out) in the file
    """

    path = fix_path(path)
    text = path.read_text()

    for k, v in kwargs.items():
        pattern = re.compile(rf"^{re.escape(k)}[ \t]*=[ \t]*[^#\s].*$", re.M)
        if (m := pattern.search(text)) is None:
            raise MoccaError(f"key not found in {path}: {k}")
        logger.info(f"mocca.ini: {m.group()} -> {k} = {v}")
        text = pattern.sub(lambda _: f"{k} = {v}", text)

    path.write_text(text)


def set_moccaslurm(
    path, job_name=None, mail_user=None, partition=None, escape_bin_restart=False
):
    """updates the mocca.slurm file

    Args:
        path (Path | str): path to mocca.slurm file
        job_name (str): job name
        mail_user (str): notification email (also uncomments the line if needed)
        partition (str): one of PARTITIONS; sets partition, time limit and memory
        escape_bin_restart (bool): run MOCCA in the escapers' restart mode
    """

    path = fix_path(path)
    assert path.is_file() and path.name == "mocca.slurm", (
        f"Not a mocca slurm file! {path=}"
    )

    subs = []  # (regex, new line)
    if job_name is not None:
        subs.append((r"#+SBATCH -J .*", f"#SBATCH -J {job_name}"))
    if mail_user is not None:
        subs.append((r"#+SBATCH --mail-user=.*", f"#SBATCH --mail-user={mail_user}"))
    if partition is not None:
        time, mem, _ = PARTITIONS[partition]
        subs += [
            (r"#+SBATCH --time=.*", f"#SBATCH --time={time}"),
            (r"#+SBATCH --mem-per-cpu=.*", f"#SBATCH --mem-per-cpu={mem}"),
            (r"#+SBATCH -p .*", f"#SBATCH -p {partition}"),
        ]
    subs.append(
        (r"\./mocca\b.*", mocca_command(escape_bin_restart)[1])
    )

    text = path.read_text()
    for regex, line in subs:
        text, n = re.subn(rf"^{regex}$", lambda _: line, text, flags=re.M)
        if n == 0:
            logger.warning(f"{path.name}: nothing to update, no line matches /{regex}/")
        else:
            logger.info(f"{path.name}: {line}")
    path.write_text(text)


def mocca_command(escape_bin_restart=False) -> tuple[list[str], str]:
    """(argv, slurm-script line) of the command running MOCCA"""
    if escape_bin_restart:
        return (
            ["./mocca", "--escape-bin-restart"],
            "./mocca --escape-bin-restart > zzz-escape-bin-restart",
        )
    return ["./mocca"], "./mocca > zzz"


def squeue_command(user=None) -> list[str]:
    """argv listing `user` (default: the current user) jobs, with a wide name column"""
    return ["squeue", "-u", user or getpass.getuser(), "-o", SQUEUE_FORMAT]


def squeue(user=None) -> None:
    """List the current user's jobs on the queue (captured and printed, like grep_mocca)"""
    cmd = squeue_command(user)
    logger.info(f"queue: {' '.join(cmd)}")
    p = run(cmd)
    if p.returncode != 0:
        raise MoccaError(f"squeue failed:\n{p.stderr.decode().strip()}")
    print(p.stdout.decode())


def srun_command(job_name, node=None) -> list[str]:
    """argv of an interactive shell on a compute node (`node` -> `-w node`, a host or a list)"""
    argv = ["srun", *SRUN_NODES, "-J", job_name, *SRUN_RES]
    if node:
        argv += ["-w", node]
    return argv + SRUN_SHELL


def srun(node=None, job_name=None) -> None:
    """Interactive shell on a compute node, replacing this process

    `mrun --srun` is therefore equivalent to running the same `srun` from the shell: the
    terminal belongs to the shell until the session ends (nothing is waited for, captured
    or logged, and there is no exit code to return).

    Raises:
        OSError: if srun cannot be executed (reported by main())
    """
    cmd = srun_command(job_name or Path.cwd().name, node)
    logger.info(f"running: {' '.join(cmd)}")
    os.execvp(cmd[0], cmd)


def prepare_inputs(path: Path, ref_dir, get_src):
    """Put mocca.ini and mocca.slurm (and *_nbody.dat from `ref_dir`) in the simulation dir

    - `ref_dir` given: its files always overwrite the ones in `path`
    - otherwise: only missing files are copied, from MOCCA's src/ defaults
      (mocca-default-2pop.ini is copied as mocca.ini); existing files are never touched
    """
    if ref_dir is not None:
        ref_dir = fix_path(ref_dir)
        for name in DEFAULT_INPUTS:
            if not (ref_dir / name).is_file():
                raise MoccaError(f"{name} not found in --from directory {ref_dir}")
        for f in [*(ref_dir / n for n in DEFAULT_INPUTS), *ref_dir.glob("*_nbody.dat")]:
            overwritten = " (overwriting)" if (path / f.name).exists() else ""
            logger.info(f"copying {f} -> {path / f.name}{overwritten}")
            shutil.copy2(f, path / f.name)
        return

    for name, default in DEFAULT_INPUTS.items():
        if (path / name).exists():
            logger.info(f"keeping existing {path / name} (use --from to overwrite)")
        else:
            src_file = get_src() / default
            logger.info(f"creating {path / name} from {src_file}")
            shutil.copy2(src_file, path / name)


def moccarun(
    path,
    user_email,
    mocca_src=None,
    ref_dir=None,
    mocca_binary=None,
    keep_mocca_binary=False,
    moccaini=None,
    partition=None,
    wait=False,
    run_sim=False,
    no_slurm=False,
    escape_bin_restart=False,
    job_name=None,
):
    """Prepare a simulation directory and, only if `run_sim`, start it.

    Preparation: mocca.ini and mocca.slurm (see prepare_inputs), the mocca binary
    (from `mocca_binary` or MOCCA's src/; skipped with `keep_mocca_binary`), then updates of
    mocca.ini (`moccaini`, `partition`) and mocca.slurm (`job_name`, `mail_user`).
    Nothing is submitted to SLURM or executed unless `run_sim` is set.
    """
    path = fix_path(path)

    if not path.is_dir():
        logger.info(f"creating directory {path}")
    path.mkdir(parents=True, exist_ok=True)

    @cache
    def get_src():
        src = resolve_mocca_src(mocca_src, path)
        logger.info(f"using MOCCA src: {src}")
        return src

    prepare_inputs(path, ref_dir, get_src)

    if keep_mocca_binary:
        if (path / "mocca").is_file():
            logger.info(f"keeping existing binary {path / 'mocca'} (--keep-mocca-binary)")
        else:
            logger.warning(f"--keep-mocca-binary given but there is no {path / 'mocca'}")
    else:
        binary = resolve_mocca_binary(mocca_binary or get_src() / "mocca")
        logger.info(f"copying binary {binary} -> {path / 'mocca'}")
        shutil.copy2(binary, path / "mocca")

    ini = dict(moccaini or {})
    if partition is not None:
        hours = PARTITIONS[partition][2]
        ini = {"runmaxcpu": int(RUNMAXCPU_FRAC * hours * 60)} | ini
    set_moccaini(path / "mocca.ini", **ini)

    set_moccaslurm(
        path / "mocca.slurm",
        job_name=job_name or path.name,
        mail_user=user_email,
        partition=partition,
        escape_bin_restart=escape_bin_restart,
    )

    if not run_sim:
        logger.info(f"prepared {path}; not started (use --run to execute)")
        return

    if not (path / "mocca").is_file():
        raise MoccaError(f"no mocca binary in {path}")

    if no_slurm:
        argv, _ = mocca_command(escape_bin_restart)
        out = "zzz-escape-bin-restart" if escape_bin_restart else "zzz"
        logger.info(f"running {' '.join(argv)} locally in {path} (output: {out})")
        with open(path / out, "w") as f:
            p = run(argv, cwd=path, stdout=f, capture_output=False)
        if p.returncode != 0:
            raise MoccaError(f"{' '.join(argv)} failed in {path}: exit code {p.returncode}")
        logger.info(f"{path.name}: local run finished")
    else:
        cmd = ["sbatch", *(["--wait"] if wait else []), "mocca.slurm"]
        logger.info(f"submitting: {' '.join(cmd)} (in {path})")
        p = run(cmd, cwd=path)
        if p.returncode != 0:
            raise MoccaError(f"cannot submit slurm job:\n{p.stderr.decode().strip()}")
        logger.info(p.stdout.decode().strip())


def make_mocca(src, opts=None) -> None:
    """Compiles MOCCA code

    Applies changes to internal params if needed and verifies a fresh binary
    was produced.

    Raises:
        MoccaError: if compilation fails or no fresh binary was produced

    Args:
        src (Path | str): path to MOCCA's src/
        opts (List[str]): options for compilation
            clean - do cleaning before compilation (forces a fresh binary)
            small | large - changes params.h to account for small or large memory usage (use only one!)
    """
    opts = set(filter(None, opts or []))
    assert not (unknown := opts - MOCCA_MAKE_OPTS), f"Unknown options: {unknown=}"

    src = fix_path(src)

    if size := next(iter(opts & MOCCA_SIZES), None):
        nmax, nbmax3, nsupzo = PARAMS_H_SIZES[size]
        params = src / "MOCCA/params.h"
        text = params.read_text()
        for key, val in {"NMAX": nmax, "NBMAX3": nbmax3, "NSUPZO": nsupzo}.items():
            text, n = re.subn(rf"\b{key}=\d+", f"{key}={val}", text)
            if n == 0:
                logger.warning(f"{params}: {key} not found, not changed")
        params.write_text(text)
        logger.info(f"{params}: NMAX={nmax}, NBMAX3={nbmax3}, NSUPZO={nsupzo} ('{size}')")

    mocca_bin = src / "mocca"
    existed_before = mocca_bin.is_file()
    bin_mtime_before = mocca_bin.stat().st_mtime if existed_before else 0

    for target in (["clean"] if "clean" in opts else []) + ["debug"]:
        logger.info(f"running 'make {target}' in {src}")
        p = run(["make", target], cwd=src, capture_output=False)
        if p.returncode != 0:
            raise MoccaError(f"compilation failed: 'make {target}' exit code {p.returncode}")
    if not mocca_bin.is_file():
        raise MoccaError(f"mocca binary not created: {mocca_bin}")
    if "clean" in opts and existed_before and mocca_bin.stat().st_mtime <= bin_mtime_before:
        raise MoccaError(f"mocca binary not rebuilt after 'make clean': {mocca_bin}")
    logger.info(f"compiled {mocca_bin}")


def grep_mocca(src, pattern) -> None:
    """grep -n `pattern` in MOCCA's Fortran sources and headers"""
    files = sorted(str(f) for f in src.rglob("*") if f.suffix in SOURCE_SUFFIXES)
    logger.info(f"grep '{pattern}' in {len(files)} files under {src}")
    p = run(["grep", "-nH", "-e", pattern, *files])
    if p.returncode == 0:
        print(p.stdout.decode())
    elif p.returncode == 1:
        logger.warning(f"no matches for '{pattern}'")
    else:
        raise MoccaError(f"grep failed: {p.stderr.decode().strip()}")


def make_opts(s):
    """Validate comma-separated --make options against MOCCA_MAKE_OPTS."""
    if unknown := set(s.split(",")) - MOCCA_MAKE_OPTS - {""}:
        raise ArgumentTypeError(f"unknown --make option(s): {sorted(unknown)}")
    return s


def parse_args(args=None):
    # Create the argument parser
    parser = ArgumentParser(
        description=f"""MOCCA simulation runner - prepare, compile and run MOCCA simulations on SLURM clusters.

Without --run nothing is submitted or executed: simulation directories are only prepared.

VERSION: {__VERSION__}
"""
    )

    # PATH
    parser.add_argument(
        "paths",
        type=Path,
        default=[],
        nargs="*",
        help="simulation directories (created if missing; default: the current one)",
    )

    parser.add_argument(
        "--grep", type=str, default=None, help="performs grep on MOCCA code files"
    )

    # MOCCA CODE AND INPUT FILES
    parser.add_argument(
        "--mocca-src",
        type=Path,
        default=None,
        help="MOCCA's src/ directory (default: <git-root>/mocca/src, else <git-root>/src); "
        "used for compilation, default input files and the mocca binary",
    )
    parser.add_argument(
        "--make",
        type=make_opts,
        nargs="?",
        default=None,
        const="",
        help="compile MOCCA in its src/ before preparing (comma-separated: clean,small,large)",
    )
    parser.add_argument(
        "--from",
        type=Path,
        default=None,
        dest="ref_dir",
        help="directory with reference mocca.ini, mocca.slurm and *_nbody.dat; "
        "they always overwrite the files in the simulation directory "
        "(by default only missing mocca.ini and mocca.slurm are created, "
        "from MOCCA's mocca-default-2pop.ini and mocca.slurm). "
        "The mocca binary is never copied from here",
    )
    parser.add_argument(
        "--mocca-binary",
        type=Path,
        default=None,
        help="copy this mocca binary (or the `mocca` in this directory) instead of <mocca-src>/mocca",
    )
    parser.add_argument(
        "-k",
        "--keep-mocca-binary",
        action="store_true",
        help="do not copy the mocca binary into the simulation directory "
        "(keep the one already there). Config files are not affected: "
        "existing ones are never overwritten unless --from is given",
    )

    # MOCCAINIT
    parser.add_argument(
        "--moccaini",
        type=json.loads,
        default=None,
        help="arguments to change in mocca.ini (JSON)",
    )

    # GRID
    parser.add_argument(
        "--grid",
        type=str,
        default=None,
        help="JSON string (or file) defining the simulation's grid",
    )

    # SLURM
    parser.add_argument(
        "--no-slurm",
        action="store_true",
        help="with --run: execute mocca locally instead of sending a slurm job",
    )
    parser.add_argument(
        "--user-email",
        type=str,
        default=None,
        help="user email for slurm notification (auto-detected from git config if not provided)",
    )
    parser.add_argument(
        "-p",
        "--partition",
        type=str,
        choices=list(PARTITIONS),
        default=None,
        help="slurm partition name (default: not change)",
    )

    # QUEUE / COMPUTE NODE
    parser.add_argument(
        "--squeue",
        action="store_true",
        help="list the current user's jobs on the queue (wide job-name column); "
        "with simulation options, listed last, after they are done",
    )
    parser.add_argument(
        "--srun",
        nargs="?",
        const="",
        default=None,
        metavar="NODE",
        help=f"interactive shell on a compute node: {' '.join(srun_command('NAME'))}; "
        "NAME is the current directory (or the given path), NODE, if given, is passed with -w; "
        "cannot be combined with other options",
    )

    # EXECUTION
    parser.add_argument(
        "-r",
        "--run",
        nargs="?",
        const=True,
        default=False,
        dest="run_sim",
        metavar="JOB_NAME",
        help="execute simulation (submit to sbatch or run locally); without it only prepare files. "
        "Optional value: the slurm job name, with placeholders {f} (simulation directory name) "
        "and {d} (0-based counter, global for all simulations of one invocation); "
        "default: the simulation directory name",
    )
    parser.add_argument(
        "--escape-bin-restart",
        action="store_true",
        help="calculate escapers evolution on a calculated simulation",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for simulation to finish (e.g. when used in a pipe)",
    )

    parser.add_argument(
        "--clean",
        nargs="?",
        const="outputs",
        default=None,
        choices=CLEAN_MODES,
        help="Clean simulation files. 'outputs' (default): keep mocca, mocca.ini, mocca.slurm, binary_nbody.dat, single_nbody.dat; 'all': keep only mocca.ini, mocca.slurm",
    )

    # MISC
    parser.add_argument("--version", action="store_true", help="show version and exit")
    parser.add_argument(
        "--logLevel",
        action="store",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="set logging level (default INFO)",
        default="INFO",
    )

    args = parser.parse_args(args)
    if args.run_sim == "":  # --run "": an empty job name is the same as no value
        args.run_sim = True
    return args


def grid_targets(base, grid_arg):
    """(path, mocca.ini changes) for every point of the grid, JSON string or file"""
    grid_file = Path(grid_arg)
    try:
        grid = json.loads(grid_file.read_text() if grid_file.is_file() else grid_arg)
    except json.JSONDecodeError as e:
        raise MoccaError(f"--grid is neither a JSON file nor a JSON string: {e}") from e

    for vals in product(*grid.values()):
        changes = dict(zip(grid.keys(), vals))
        name = "_".join(f"{k}={v}" for k, v in changes.items()).replace(" ", "")
        yield base / name, changes


def paths_of(args) -> list[Path]:
    """simulation directories: the positional paths, or the current one if none was given"""
    return args.paths or [Path(".")]


def given_options(args, dests) -> list[str]:
    """the options of `dests` that were given, as --option names (a bare flag counts)"""
    return [
        "--" + OPTION_NAMES.get(d, d).replace("_", "-")
        for d in dests
        if getattr(args, d, None) not in (None, False)
    ]


def work_requested(args) -> bool:
    """True if a simulation has to be prepared or run, so that --squeue comes after it"""
    return bool(args.paths) or any(
        getattr(args, d) is not None for d in ("make", "clean", "grid")
    ) or args.run_sim


def execute_srun(args) -> int:
    """--srun: an interactive shell, alone or with a single path naming the job"""
    if len(args.paths) > 1:
        raise MoccaError(f"--srun takes at most one path, given {len(args.paths)}")
    if others := given_options(args, SRUN_EXCLUSIVE):
        raise MoccaError(f"--srun cannot be combined with {', '.join(others)}")
    job_name = args.paths[0].name if args.paths else Path.cwd().name
    srun(args.srun or None, job_name=job_name)
    return 0  # not reached: srun replaces this process


def execute(args) -> int:
    """Run the requested actions: --srun alone, or simulations and finally --squeue"""
    if args.srun is not None:
        return execute_srun(args)

    paths = paths_of(args)

    if args.grep is not None:
        grep_mocca(resolve_mocca_src(args.mocca_src, paths[0]), args.grep)
        rc = 0
    elif args.squeue and not work_requested(args):
        rc = 0  # nothing to prepare: the queue listing is all that was asked for
        if ignored := given_options(args, SQUEUE_IGNORED):
            logger.warning(f"--squeue only: ignoring {', '.join(ignored)}")
    else:
        rc = execute_simulations(args)

    if args.squeue:
        squeue()
    return rc


def execute_simulations(args) -> int:
    """Prepare (and, with --run, start) every simulation; returns 0 if all succeeded"""
    paths = paths_of(args)

    # (path, extra mocca.ini changes) for every simulation
    if args.grid is not None:
        if len(paths) != 1:
            raise MoccaError(f"--grid needs exactly one path, given {len(paths)}")
        targets = list(grid_targets(paths[0], args.grid))
        logger.info(f"grid: {len(targets)} simulation(s) in {fix_path(paths[0])}")
    else:
        targets = [(p, {}) for p in paths]

    user_email = get_user_email(args.user_email)

    # compile once, then per simulation: clean -> prepare -> run
    if args.make is not None:
        make_mocca(
            resolve_mocca_src(args.mocca_src, targets[0][0]), opts=args.make.split(",")
        )

    failed = []
    for i, (path, changes) in enumerate(targets):
        logger.info(f"== {fix_path(path)}")
        try:
            if args.clean is not None:
                if path.is_dir():
                    clean_dir(path, keep=CLEAN_MODES[args.clean])
                else:
                    logger.info(f"--clean: {path} does not exist yet, nothing to clean")
            job_name = args.run_sim if isinstance(args.run_sim, str) else None
            if job_name is not None:
                try:
                    job_name = job_name.format(f=path.name, d=i)
                except (KeyError, IndexError):
                    raise MoccaError(f"bad --run job name template: {args.run_sim}")
            moccarun(
                path,
                user_email,
                mocca_src=args.mocca_src,
                ref_dir=args.ref_dir,
                mocca_binary=args.mocca_binary,
                keep_mocca_binary=args.keep_mocca_binary,
                moccaini=(args.moccaini or {}) | changes,
                partition=args.partition,
                wait=args.wait,
                run_sim=bool(args.run_sim),
                no_slurm=args.no_slurm,
                escape_bin_restart=args.escape_bin_restart,
                job_name=job_name,
            )
        except (MoccaError, OSError) as e:
            logger.error(f"{path}: {e}")
            failed.append(path)

    done = len(targets) - len(failed)
    what = "started" if args.run_sim else "prepared, not started (use --run)"
    logger.info(f"finished: {done}/{len(targets)} simulation(s) {what}")
    if failed:
        logger.error(f"failed: {', '.join(str(p) for p in failed)}")
    return 1 if failed else 0


def setup_logging(level="INFO"):
    """Log to stderr: `LEVEL message`; DEBUG adds time and code location"""
    fmt = "<level>{level: <7}</level> {message}"
    if level == "DEBUG":
        fmt = "<green>{time:HH:mm:ss}</green> " + fmt + " <dim>({function}:{line})</dim>"
    logger.remove()
    logger.add(sys.stderr, level=level, format=fmt)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(args.logLevel)

    if args.version:
        print(f"mrun {__VERSION__}")
        return 0

    logger.debug(f"{args=}")
    try:
        return execute(args)
    except MoccaError as e:
        logger.error(e)
    except OSError as e:
        logger.error(f"{type(e).__name__}: {e}")
    except KeyboardInterrupt:
        logger.error("interrupted")
    return 1


if __name__ == "__main__":
    sys.exit(main())

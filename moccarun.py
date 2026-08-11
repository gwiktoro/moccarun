#!/usr/bin/env python3

__VERSION__ = "2608111845"

import os
import sys
from argparse import ArgumentParser, ArgumentTypeError
from configparser import ConfigParser
from copy import copy
from itertools import product
from pathlib import Path
from shutil import rmtree
import subprocess
import json

import warnings

from loguru import logger

MOCCA_SIZES = {"small", "large"}
MOCCA_MAKE_OPTS = MOCCA_SIZES | {"find", "clean"}
CLEAN_MODES = {
    "all": ["mocca.ini", "mocca.slurm"],
    "outputs": ["mocca", "mocca.ini", "mocca.slurm", "binary_nbody.dat", "single_nbody.dat"],
}


def get_user_email(cli_email: str | None = None) -> str:
    """Get user email for SLURM notifications.

    Priority: CLI arg > MOCCARUN_EMAIL env > ~/.gitconfig > error
    """
    if cli_email:
        return cli_email

    if env_email := os.environ.get("MOCCARUN_EMAIL"):
        return env_email

    gitconfig = Path.home() / ".gitconfig"
    if gitconfig.is_file():
        parser = ConfigParser()
        parser.read(gitconfig)
        if parser.has_option("user", "email"):
            return parser.get("user", "email")
        logger.warning("No email found in ~/.gitconfig, trying system default")

    if system_email := os.environ.get("EMAIL"):
        return system_email

    raise ValueError(
        "No email provided. Set --user-email, MOCCARUN_EMAIL env var, "
        "configure git (git config --global user.email), or set EMAIL env var."
    )


def fix_path(path):
    """ensure that the path is Path() class and is absolute"""

    return Path(path).absolute()


def clean_dir(path, keep=None):
    """Cleans the target directory from all files except those specified in `keep`"""

    path = fix_path(path)
    keep = keep or []

    for item in path.iterdir():
        if item.name not in keep:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                rmtree(item)


def verify_cleaned(path, keep=None):
    """Verify only `keep` files remain after cleaning; return False if leftovers exist."""
    path = fix_path(path)
    keep = set(keep or [])
    leftover = [item.name for item in path.iterdir() if item.name not in keep]
    if leftover:
        logger.error(f"unexpected files remaining after clean: {sorted(leftover)}")
        return False
    return True


def find_mocca_src_path(path=None):
    """Find the MOCCA src/ directory using git repository root.

    Args:
        path: Starting path (default: current directory)

    Returns:
        Path to src/ directory if valid, None otherwise
    """
    if path is None:
        path = Path.cwd()
    else:
        path = fix_path(path)

    p = run("git rev-parse --show-toplevel")
    if p.returncode != 0:
        return None

    repo_root = Path(p.stdout.decode().strip())
    src_path = repo_root / "src"

    if (
        src_path.is_dir()
        and (src_path / "mocca-default-2pop.ini").is_file()
        and (src_path / "MOCCA").is_dir()
        and (src_path / "bse").is_dir()
    ):
        return src_path

    return None


def find_mocca_binary(path=None):
    """Find the mocca binary in the git repo's src/ directory.

    Uses find_mocca_src_path() to locate src/, then checks for mocca binary.

    Args:
        path: Starting path (default: current directory)

    Returns:
        Path to the mocca binary

    Raises:
        SystemExit: If binary is not found and no alternative is provided
    """
    src_path = find_mocca_src_path(path)
    if src_path is not None:
        mocca_binary = src_path / "mocca"
        if mocca_binary.is_file():
            return mocca_binary

    logger.error(
        "mocca binary not found in git repo's src/ directory. "
        "Use --mocca-binary KEEP to keep the existing binary, "
        "or --mocca-binary /path/to/mocca to specify a path."
    )
    exit(1)


def run(cmd, **kwargs):
    """Run subprocess command

    assuming shell=True and capture_output=True if not specified in kwargs

    Args
        cmd (str): command to run
        **kwargs : passed to subprocess.run()
    Returns
        subprocess.CompletedProcess
    """
    kwargs.setdefault("shell", True)
    kwargs.setdefault("capture_output", True)

    logger.debug(f"run {cmd=} {kwargs=}")
    p = subprocess.run(cmd, **kwargs)
    return p


def set_moccaini(path, **kwargs):
    """make changes to mocca.ini file

    Args:
        path (Path | str): path to mocca.ini file
        kwargs: key and values to update

    Returns:
        0 on success, 1 if a key was not found
    """

    path = fix_path(path)
    assert path.is_file(), f"not a file: {path=}"

    for k, v in kwargs.items():
        p = run(rf'grep "^{k}\s*=\s*[^#]\+" {path}')
        if p.returncode == 1:
            logger.error(f"key not found in mocca.ini: {k=}")
            return 1
        p_sed = run(rf'sed -i "s/^{k}\s*=\s*.*/{k} = {v}/" {path}')
        assert p_sed.returncode == 0, "sed run incorrectly! {p_sed.args=}"
        logger.info(f"{p.stdout.decode('utf8').strip()} -> {v}")

    return 0


def set_moccaslurm(
    path, job_name=None, mail_user=None, partition=None, escape_bin_restart=False
):
    """updates the mocca.slurm file

    Args:
        path (Path | str): path to mocca.slurm file
    """

    path = fix_path(path)
    assert path.is_file() and path.name == "mocca.slurm", (
        f"Not a mocca slurm file! {path=}"
    )

    sed_cmd_l = []

    if job_name is not None:
        sed_cmd_l.append(f"s/#SBATCH -J .*/#SBATCH -J {job_name}/")
    if mail_user is not None:
        sed_cmd_l.append(f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={mail_user}/")
    if partition is not None:
        if partition == "short":
            sed_cmd_l.append("s/#SBATCH --time=.*/#SBATCH --time=36:00:00/")
            sed_cmd_l.append("s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
            sed_cmd_l.append("s/#SBATCH -p .*/#SBATCH -p short/")
        elif partition == "long":
            sed_cmd_l.append("s/#SBATCH --time=.*/#SBATCH --time=336:00:00/")
            sed_cmd_l.append("s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
            sed_cmd_l.append("s/#SBATCH -p .*/#SBATCH -p long/")
        elif partition == "bigmem":
            sed_cmd_l.append("s/#SBATCH --time=.*/#SBATCH --time=168:00:00/")
            sed_cmd_l.append("s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=5999MB/")
            sed_cmd_l.append("s/#SBATCH -p .*/#SBATCH -p bigmem/")
        else:
            logger.error(f"Unsupported partition type! {partition=}")
            exit(1)

    if escape_bin_restart:
        sed_cmd_l.append(
            r"s/^.\/mocca.*/.\/mocca --escape-bin-restart > zzz-escape-bin-restart/"
        )
    else:
        sed_cmd_l.append(r"s/^\.\/mocca.*/.\/mocca > zzz/")

    sed_cmd = ";".join(sed_cmd_l)
    run(f'sed -i "{sed_cmd}" {path}')


def moccarun(
    path=Path("."),
    mocca_src_path=None,
    ref_dir=None,
    mocca_binary="FIND",
    moccaini=None,
    user_email=None,
    partition=None,
    wait=False,
    dry_run=False,
    run_sim=False,
    no_slurm=False,
    escape_bin_restart=False,
    moccainipath=None,
    **kwargs,
):
    user_email = get_user_email(user_email)
    moccaini = moccaini or {}

    logger.debug(f"Unknown arguments to moccarun(): {kwargs}")

    path = fix_path(path)
    logger.debug(f"{path=}")

    if not path.exists():
        logger.info(f"Creating directory {path}")
        run(f"mkdir -p {path}")
        if ref_dir is None:
            mocca_src_path = mocca_src_path or find_mocca_src_path(path)
            assert mocca_src_path is not None, "no path to MOCCA's src/"
            logger.info(f"populating initial files from {mocca_src_path=}")
            run(
                f"cp -f {mocca_src_path}/mocca-default-2pop.ini {path}/mocca.ini && cp -f {mocca_src_path}/mocca.slurm {path}"
            )

    if ref_dir is not None:
        run(f"cp -f {ref_dir}/{{mocca.ini,mocca.slurm,*_nbody.dat}} {path}")
    if moccainipath is not None:
        run(f"cp -f {moccainipath} {path}")

    if set_moccaini(path / "mocca.ini", **moccaini):
        exit(1)

    if mocca_binary != "KEEP":
        if mocca_binary == "FIND":
            mocca_binary_path = find_mocca_binary(path)
        else:
            if not mocca_binary.endswith("/mocca"):
                mocca_binary += "/mocca"
            mocca_binary_path = fix_path(mocca_binary)

        logger.debug(f"{mocca_binary_path=}")

        p = run(f"cp {mocca_binary_path} {path}")
        if p.returncode != 0:
            logger.error(f"Mocca binary not found in {mocca_binary_path=}")
            exit(1)

    # SLURM
    logger.info("Updating slurm script")

    set_moccaslurm(
        path / "mocca.slurm",
        job_name=path.name,
        mail_user=user_email,
        partition=partition,
        escape_bin_restart=escape_bin_restart,
    )

    # Updating the runmaxcpu parameter for partition
    runmaxcpu_frac = 0.9  # fraction of partitions max time at which the code is gently stopped (for restarts)
    if partition is not None:
        if partition == "short":
            set_moccaini(path / "mocca.ini", runmaxcpu=int(runmaxcpu_frac * 2160))
        elif partition == "long":
            set_moccaini(path / "mocca.ini", runmaxcpu=int(runmaxcpu_frac * 20160))
        elif partition == "bigmem":
            set_moccaini(path / "mocca.ini", runmaxcpu=int(runmaxcpu_frac * 10080))
        else:
            logger.error(f"Unsupported partition type! {partition=}")
            exit(1)

    if run_sim:
        if no_slurm:
            run(f"(cd {path} && ./mocca > zzz)")
        else:
            p = run(f"(cd {path} && sbatch {'--wait' if wait else ''} mocca.slurm)")
            assert p.returncode == 0, "cannot submit slurm job:\n{p.args=}\n{p.strerr=}"
            logger.info(f"{p.stdout.decode('utf8').strip()}")
    else:
        logger.info("dry run finished")


def make_mocca(path, opts=None) -> None:
    """Compiles MOCCA code

    Applies changes to internal params if needed and verifies a fresh binary
    was produced. On failure, logs an error and exits.

    CHANGELOG: changes to Mcluster/main.c are no longer needed with the new code

    Args:
        path (Path | str): path to src (see also 'find' option below)
        opts (List[str]): options for compilation
            clean - do cleaning before compilation (forces a fresh binary)
            find - find the MOCCA src directory via git repository root
            small | large - changes params.h to account for small or large memory usage (use only one!)
    """
    opts = set(filter(None, opts or []))
    assert not (unknown := opts - MOCCA_MAKE_OPTS), f"Unknown options: {unknown=}"

    path = fix_path(path)

    if "find" in opts:
        path = find_mocca_src_path(path)

    size = next(iter(opts & MOCCA_SIZES), None)
    if size is not None:
        sed_cmd = {
            "small": r"s/NMAX=[0-9]\+/NMAX=2200000/;s/NBMAX3=[0-9]\+/NBMAX3=2200000/;s/NSUPZO=[0-9]\+/NSUPZO=400/",
            "large": r"s/NMAX=[0-9]\+/NMAX=5200000/;s/NBMAX3=[0-9]\+/NBMAX3=5200000/;s/NSUPZO=[0-9]\+/NSUPZO=600/",
        }[size]
        run(f'sed -i "{sed_cmd}" {path / "MOCCA/params.h"}')

    mocca_bin = path / "mocca"
    existed_before = mocca_bin.is_file()
    bin_mtime_before = mocca_bin.stat().st_mtime if existed_before else 0

    cmd = f"(cd {path} &&"
    if "clean" in opts:
        cmd += " make clean &&"
    cmd += " make debug)"
    p = run(cmd, capture_output=False)
    if p.returncode != 0:
        logger.error(f"Compilation failed: exit code {p.returncode}")
        exit(1)
    if not mocca_bin.is_file():
        logger.error(f"mocca binary not created: {mocca_bin}")
        exit(1)
    if "clean" in opts and existed_before and mocca_bin.stat().st_mtime <= bin_mtime_before:
        logger.error(f"mocca binary not rebuilt after 'make clean': {mocca_bin}")
        exit(1)


def make_opts(s):
    """Validate comma-separated --make options against MOCCA_MAKE_OPTS."""
    if unknown := set(s.split(",")) - MOCCA_MAKE_OPTS - {""}:
        raise ArgumentTypeError(f"unknown --make option(s): {sorted(unknown)}")
    return s


def parse_args(args=None):
    # Create the argument parser
    parser = ArgumentParser(
        description=f"""MOCCA simulation runner - compile and run MOCCA code on SLURM clusters.

VERSION: {__VERSION__}
"""
    )

    # PATH
    parser.add_argument(
        "paths",
        type=Path,
        default=[Path(".")],
        nargs="*",
        help="paths to directories with mocca.ini and mocca.slurm",
    )

    parser.add_argument(
        "--grep", type=str, default=None, help="performs grep on MOCCA code files"
    )

    # MOCCA BINARY
    parser.add_argument(
        "--make", type=make_opts, nargs="?", default=None, const="", help="compile MOCCA (comma-separated: clean,find,small,large)",
    )
    parser.add_argument(
        "--from",
        type=str,
        default=None,
        dest="ref_dir",
        help="Directory with reference files (mocca.ini, mocca.slurm, *_nbody.dat)",
    )
    parser.add_argument(
        "--moccainipath",
        type=Path,
        default=None,
        help="path to mocca.ini file. Will be copied to simulation directory",
    )
    parser.add_argument(
        "--mocca-binary",
        action="store",
        type=str,
        default="FIND",
        help="Defines how to obtain the `mocca` binary file. 'FIND' (default) - look for mocca binary in git repo's src/; 'KEEP' - keep the current `mocca` binary (must be present); otherwise, treated as path to the mocca binary or the folder where it's located",
    )

    # MOCCAINIT
    parser.add_argument(
        "--moccaini",
        type=json.loads,
        default=None,
        help="arguments to change in mocca.ini",
    )

    # GRID
    parser.add_argument(
        "--grid",
        type=str,
        default=None,
        help="JSON string defining the simulation's grid",
    )

    # SLURM
    parser.add_argument(
        "--no-slurm",
        action="store_true",
        help="do not send slurm job, but execute code normally",
    )
    parser.add_argument(
        "--user-email",
        type=str,
        default=None,
        help="user email for slurm notification (auto-detected from gitconfig if not provided)",
    )
    parser.add_argument(
        "-p",
        "--partition",
        type=str,
        choices=["short", "long", "bigmem"],
        default=None,
        help="slurm partition name (default: not change)",
    )

    # EXECUTION
    parser.add_argument(
        "-r",
        "--run",
        action="store_true",
        default=False,
        dest="run_sim",
        help="execute simulation (submit to sbatch or run locally)",
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
        "--dry-run",
        action="store_true",
        help="[deprecated] dry-run is now the default; use --run to execute",
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
        help="set logging level (default WARNING)",
        default="WARNING",
    )

    # Parse the command-line arguments
    args = parser.parse_args(args)

    return args


def main():
    args = parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.logLevel)

    if args.version:
        print(f"mrun {__VERSION__}")
        return 0

    if args.dry_run:
        warnings.warn(
            "--dry-run is deprecated; the default is now dry-run (use --run to execute)",
            DeprecationWarning,
            stacklevel=2,
        )

    # logger.parent.setLevel(args.logLevel)
    logger.debug(f"{args=}")
    del args.logLevel

    logger.debug(f"{args.paths=}")
    logger.debug(f"{args.make=}")

    # Start a grid of simulations
    if args.grid is not None:
        if len(args.paths) != 1:
            logger.error(
                f"paths must be a single Path for '--grid' ({len(args.paths)=})"
            )
            return 1
        grid_path = args.paths[0]
        grid_json = args.grid
        del args.grid
        del args.paths

        if args.make is not None:
            make_mocca(find_mocca_src_path(grid_path), opts=args.make.split(","))
        if args.clean is not None:
            clean_dir(grid_path, keep=CLEAN_MODES[args.clean])
            if not verify_cleaned(grid_path, CLEAN_MODES[args.clean]):
                return 1

        grid_file = Path(grid_json)
        grid = json.loads(grid_file.read_text() if grid_file.exists() else grid_json)

        for vals in product(*grid.values()):
            args.moccaini = dict(zip(grid.keys(), vals))
            logger.debug(f"{args.moccaini=}")

            moccarun(
                grid_path
                / "_".join(f"{k}={v}" for k, v in args.moccaini.items()).replace(
                    " ", ""
                ),
                **vars(args),
            )
        return 0

    # Execute: linear chain per path (compile -> clean -> run)
    for rp in args.paths:
        run_args = copy(args)
        run_args.path = rp
        logger.debug(f"{run_args=}")

        if run_args.grep is not None:
            logger.debug("grep")
            path = find_mocca_src_path(run_args.path)
            p = run(
                rf"""find {path} -type f \( -name "*.f" -o -name "*.f90" -o -name "*.f95" -o -name "*.f03" -o -name "*.f08" -o -name "*.h" \) -print0 | xargs -0 grep -n {run_args.grep} """
            )
            if p.returncode == 0:
                print(p.stdout.decode("utf8"))
            else:
                print(p.stderr.decode("utf8"))

            continue

        if run_args.make is not None:
            make_mocca(find_mocca_src_path(rp), opts=run_args.make.split(","))
        if run_args.clean is not None:
            clean_dir(rp, keep=CLEAN_MODES[run_args.clean])
            if not verify_cleaned(rp, CLEAN_MODES[run_args.clean]):
                continue
        logger.info(f"Using path: {rp}")
        moccarun(**vars(run_args))


if __name__ == "__main__":
    main()

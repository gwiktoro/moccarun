# AGENTS.md

## Project Overview
MOCCA simulation runner for SLURM clusters. Python 3.13 required.

## Running the Script
Default is dry-run (only prepares files); `-r`/`--run` submits to sbatch.
```bash
mrun path/to/simulation -p short --run
uv run python moccarun.py path/to/simulation
```

## Versioning
- Auto-bumped by `.githooks/pre-commit` to timestamp `YYMMDDHHMM` in `moccarun.py` and `pyproject.toml`.
- Enable hook: `make setup-hooks` (git config core.hooksPath .githooks).
- Tests assert this format (`test_version.py`).

## MOCCA Discovery and Preparation
- MOCCA src: `<git-root>/mocca/src`, else `<git-root>/src` (first wins; `find_mocca_src_path()`, git root of the simulation path, not cwd); `--mocca-src` overrides. All validated by `validate_mocca_src()`: parent of src is its own git root, a git remote URL is named `mocca` (`MOCCA_REPO_NAME`), `MOCCA_SRC_TRACKED` paths are tracked by git, makefile has a `mocca:` target, default inputs exist.
- Prep: `mocca.ini`/`mocca.slurm` copied from src defaults only if missing; `--from` always overwrites (and brings `*_nbody.dat`, never the binary). Binary copied from `<src>/mocca` or `--mocca-binary`; `-k`/`--keep-mocca-binary` skips it.
- Nothing is submitted/executed without `--run` (single gate in `moccarun()`). `--run` takes an optional job-name value: `--run "job_{f}_{d}"` (`{f}` = simulation dir name, `{d}` = 0-based global counter; default: dir name). Paths go before `--run` or after its value.
- `--make` compiles once per execution, before any preparation.
- Logging (loguru, stderr, default INFO via `setup_logging()`): every action/skip/rejection must be logged; expected failures raise `MoccaError`, reported once by `execute()` per simulation (others continue, exit code 1) or by `main()`. Tests: `tests/test_logging.py`.

## Queue and Compute Node
- `--squeue`: `squeue -u <current user> -o SQUEUE_FORMAT` (wide job-name column `%.48j`), captured, printed and failure -> `MoccaError` (`squeue_command()`, `squeue()`). It runs **last** in `execute()`, after `--grep` or the simulations; alone (nothing to prepare, `work_requested()` false) no simulation is prepared and preparation-only options are reported as ignored (`SQUEUE_IGNORED`).
- `--srun [NODE]`: `srun -N 1 -J <job> --mem-per-cpu=8GB -p bigmem [-w NODE] --pty bash` (`SRUN_NODES`, `SRUN_RES`, `SRUN_SHELL`, `srun_command()`). `srun()` `os.execvp`s it: `mrun` becomes `srun` (terminal owned by the session, nothing waited for/captured/logged, no exit code); a missing `srun` binary is an `OSError` reported by `main()`. Job name = current directory name, or the single given path. Exclusive: rejected with any other option (`SRUN_EXCLUSIVE`), or with more than one path.
- Positional `paths` default to `[]`; `paths_of(args)` resolves them to the current directory when none is given.

## Makefile
Targets: `install` (uv tool install .), `test`, `sync` (--extra dev), `setup-hooks`, `clean`.

## Email for SLURM Notifications
Auto-detected in this priority:
1. `--user-email` CLI argument
2. `MOCCARUN_EMAIL` environment variable
3. `git config user.email`
4. `EMAIL` environment variable
5. Error if none found

## Testing
```bash
uv run pytest
```

## Package Management
Uses `uv` (lockfile exists). Dependencies: `loguru>=0.7.3`. Dev: `pytest>=9.0.3`.

## Files
- `moccarun.py` - Main CLI entry point
- `tests/` - Test suite (cli, email, version, mocca_src, prepare, slurm); `conftest.py` builds a fake MOCCA git repo and holds the `log` fixture / `has(log, level, text)` helper
- `Makefile` - install/test/sync/setup-hooks targets
- `.githooks/pre-commit` - version auto-bump hook
- `.github/workflows/test.yml` - CI (install + mrun --version + pytest)

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

## Binary Discovery
`mocca` binary is found via git root → `src/mocca` (`find_mocca_src_path()`).

## Makefile
Targets: `install` (uv tool install .), `test`, `sync` (--extra dev), `setup-hooks`, `clean`.

## Email for SLURM Notifications
Auto-detected in this priority:
1. `--user-email` CLI argument
2. `MOCCARUN_EMAIL` environment variable
3. `~/.gitconfig` user.email
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
- `tests/` - Test suite (cli, email, version)
- `Makefile` - install/test/sync/setup-hooks targets
- `.githooks/pre-commit` - version auto-bump hook
- `.github/workflows/test.yml` - CI (install + mrun --version + pytest)

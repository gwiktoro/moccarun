# AGENTS.md

## Project Overview
MOCCA simulation runner for SLURM clusters. Python 3.13 required.

## Running the Script
```bash
mrun path/to/simulation --partition short
uv run python moccarun.py path/to/simulation
```

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

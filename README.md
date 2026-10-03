# MOCCARUN

MOCCA simulation runner for SLURM clusters.

## Installation

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
make install
```

Installs the `mrun` CLI from the current branch (`uv tool install .`). Optionally enable the pre-commit hook that auto-stamps the version:

```bash
make setup-hooks
```

## Quick Start

```bash
# Prepare a simulation directory (default: dry-run, no submission)
mrun path/to/simulation

# Run it (submit to sbatch)
mrun path/to/simulation --run

# Short alias for --partition
mrun path/to/simulation -p short

# Override mocca.ini parameters
mrun path/to/simulation --moccaini '{"tdelay_fraction": 0.0}'

# Compile MOCCA (once), then prepare
mrun path/to/simulation --make clean,large

# Start from another simulation's mocca.ini, mocca.slurm, *_nbody.dat (always overwrites)
mrun path/to/simulation --from path/to/reference

# Grid of simulations
mrun path/to/grid --grid '{"n": [1000, 2000]}' --from path/to/reference

# Clear outputs, keeping mocca.ini and mocca.slurm
mrun path/to/simulation --clean

# Clear everything except binary and data files
mrun path/to/simulation --clean all
```

## Key Features

- **Default is dry-run**: `mrun` only prepares files; use `-r`/`--run` to submit to sbatch
- **Linear chaining**: `--make`, `--clean`, `--run` compose as compile → clean → run per path
- **`--clean`**: clean output files (`outputs` keeps binary+data files; `all` keeps only ini+slurm)
- **Paths are positional**: place them before option values, e.g. `mrun path/to/sim --make clean,large`. A path after `--make`/`--clean` is rejected as an unexpected option value
- **MOCCA code**: looked up in `<git-root>/mocca/src` (MOCCA as a submodule/subdirectory of your project), else `<git-root>/src` (inside MOCCA's own repository); the first takes precedence. A candidate is accepted only if its git repository is named `mocca` on a remote and MOCCA-specific files are tracked by git there. Override with `--mocca-src PATH` (verified the same way)
- **Preparation** (default `mrun`): creates the directory; copies `mocca.ini` (from `mocca-default-2pop.ini`) and `mocca.slurm` from MOCCA's `src/` **only if missing** (existing files are never overwritten, but `--moccaini`, `-p`, email, job name are still applied); `--from DIR` always overwrites them from `DIR`
- **`mocca` binary**: copied from `<mocca-src>/mocca` (after `--make`, if given) on every run, never from `--from`. `--mocca-binary PATH` copies a specific binary instead; `-k`/`--keep-mocca-binary` does not copy it (keeps the existing one)
- **Logging**: every action (directories created, files copied/kept/overwritten, `mocca.ini`/`mocca.slurm` edits, compilation, submission, cleaning), warning and rejection is logged to stderr at the default `INFO` level; a failing simulation does not stop the others, a summary is printed and the exit code is 1. `--logLevel DEBUG` adds the executed commands, `WARNING`/`ERROR` quiet it down
- **Nothing runs without `--run`**: no `sbatch` (or local `--no-slurm` execution) otherwise
- **Email**: auto-detected from CLI arg, env var, or git config

## Email

SLURM notifications use email auto-detected in this priority:
1. `--user-email` CLI arg
2. `MOCCARUN_EMAIL` env var
3. `git config user.email`
4. `EMAIL` env var

## Development

```bash
make sync        # uv sync --extra dev
make test        # uv run pytest
make setup-hooks # enable pre-commit hook (auto-stamps version YYMMDDHHMM)
make clean
```

---

## License

See [LICENSE](LICENSE) for details.

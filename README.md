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

# Compile and prepare
mrun --make clean,large path/to/simulation

# Grid of simulations
mrun --grid '{"nbody": [1000, 2000]}' --from path/to/reference

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
- **Binary discovery**: finds `mocca` binary in `src/` of the git repository root
- **Email**: auto-detected from CLI arg, env var, or gitconfig

## Email

SLURM notifications use email auto-detected in this priority:
1. `--user-email` CLI arg
2. `MOCCARUN_EMAIL` env var
3. `~/.gitconfig` user.email
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

# MOCCARUN

MOCCA simulation runner for SLURM clusters.

## Installation

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install moccarun
```

When installing from a non-master branch, use `--name mrun-dev` to keep `mrun` from master available:

```bash
uv tool install --name mrun-dev git+https://github.com/user/moccarun@branch
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
mrun path/to/simulation --clear

# Clear everything except binary and data files
mrun path/to/simulation --clear all
```

## Key Features

- **`--run`/`-r`**: Execute the simulation (default is dry-run, which only prepares files)
- **`-p`**: Shorthand for `--partition` (choices: `short`, `long`, `bigmem`)
- **`--clear`**: Clean simulation output files (`outputs` mode keeps binary+data by default; `all` keeps only ini+slurm)
- **Binary discovery**: Automatically finds `src/mocca` in the git repository root
- **Email**: Auto-detected from CLI arg, env var, or gitconfig

## Email

SLURM notifications use email auto-detected in this priority:
1. `--user-email` CLI arg
2. `MOCCARUN_EMAIL` env var
3. `~/.gitconfig` user.email
4. `EMAIL` env var

## Development

```bash
uv sync --extra dev
uv run pytest
```

---

## License

See [LICENSE](LICENSE) for details.

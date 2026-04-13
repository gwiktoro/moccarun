# MOCCARUN
by Grzegorz Wiktorowicz

MOCCA simulation runner for SLURM clusters.

## Installation

Requires Python 3.13+.

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install mrun (non-editable, stable)
uv tool install moccarun

# 3. Verify
mrun --version
```

## Quick Start

```bash
# Run simulation
mrun path/to/simulation --partition short

# Run with custom parameters
mrun path/to/simulation --moccaini '{"tdelay_fraction": 0.0}'

# Compile code first
mrun --make clean,large path/to/simulation

# Parameter sweep
mrun --grid '{"nbody": [1000, 2000]}' --ref-dir path/to/reference
```

## Email
SLURM notifications use email auto-detected in this priority:
1. `--user-email` CLI arg
2. `MOCCARUN_EMAIL` env var
3. `~/.gitconfig` user.email
4. `EMAIL` env var

---

## License
MIT License

## Library
```python
import moccalib as ml
```

---

## TODO / Known Issues

- [ ] Merge `extract_snapshot.py` into main CLI
- [ ] Merge `test_snapshots.py` into main CLI
- [ ] Validate `moccaini` keys against known parameters
- [ ] Add GitHub Actions CI (for public releases only - not available for private repos)
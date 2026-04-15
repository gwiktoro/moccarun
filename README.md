# MOCCARUN

MOCCA simulation runner for SLURM clusters.

## Installation

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install moccarun
```

## Quick Start

```bash
mrun path/to/simulation --partition short
mrun path/to/simulation --moccaini '{"tdelay_fraction": 0.0}'
mrun --make clean,large path/to/simulation
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

See [LICENSE](LICENSE) for details.

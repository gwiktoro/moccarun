import json
import pytest
from moccarun import parse_args


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_grid_accepts_json_string(self):
        """--grid should accept JSON string."""
        args = parse_args(["--grid", '{"n": [1, 2]}', "."])
        assert args.grid == '{"n": [1, 2]}'

    def test_moccaini_parses_json(self):
        """--moccaini should parse JSON."""
        args = parse_args(["--moccaini", '{"n": 100}', "."])
        assert args.moccaini == {"n": 100}

    def test_partition_short(self):
        """--partition short should be accepted."""
        args = parse_args(["--partition", "short", "."])
        assert args.partition == "short"

    def test_partition_long(self):
        """--partition long should be accepted."""
        args = parse_args(["--partition", "long", "."])
        assert args.partition == "long"

    def test_partition_bigmem(self):
        """--partition bigmem should be accepted."""
        args = parse_args(["--partition", "bigmem", "."])
        assert args.partition == "bigmem"

    def test_partition_invalid_rejected(self):
        """Invalid partition should be rejected."""
        with pytest.raises(SystemExit):
            parse_args(["--partition", "invalid", "."])

    def test_log_level_default(self):
        """Default log level should be WARNING."""
        args = parse_args(["."])
        assert args.logLevel == "WARNING"

    def test_log_level_can_be_changed(self):
        """Log level should be configurable."""
        args = parse_args(["--logLevel", "DEBUG", "."])
        assert args.logLevel == "DEBUG"

    def test_version_flag_accepted(self):
        """--version flag should be accepted."""
        args = parse_args(["--version"])
        assert args.version is True

    def test_dry_run_flag(self):
        """--dry-run should be accepted."""
        args = parse_args(["--dry-run", "."])
        assert args.dry_run is True

    def test_no_slurm_flag(self):
        """--no-slurm should be accepted."""
        args = parse_args(["--no-slurm", "."])
        assert args.no_slurm is True

    def test_default_paths_is_current_dir(self):
        """Default path should be current directory."""
        from pathlib import Path

        args = parse_args([])
        assert args.paths == [Path(".")]

    def test_multiple_paths_accepted(self):
        """Multiple paths should be accepted."""
        args = parse_args(["path1", "path2", "path3"])
        assert len(args.paths) == 3

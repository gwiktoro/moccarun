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


class TestClearArg:
    """Tests for --clear argument parsing."""

    def test_clear_without_value_defaults_to_outputs(self):
        """--clear without value should default to 'outputs'."""
        args = parse_args([".", "--clear"])
        assert args.clear == "outputs"

    def test_clear_all(self):
        """--clear all should be accepted."""
        args = parse_args([".", "--clear", "all"])
        assert args.clear == "all"

    def test_clear_outputs(self):
        """--clear outputs should be accepted."""
        args = parse_args([".", "--clear", "outputs"])
        assert args.clear == "outputs"

    def test_clear_default_is_none(self):
        """Default should be None (not set)."""
        args = parse_args(["."])
        assert args.clear is None


class TestPartitionAlias:
    """Tests for -p shorthand for --partition."""

    def test_partition_via_p(self):
        """-p short should work as --partition short."""
        args = parse_args(["-p", "short", "."])
        assert args.partition == "short"

    def test_partition_via_long(self):
        """--partition should still work."""
        args = parse_args(["--partition", "bigmem", "."])
        assert args.partition == "bigmem"


class TestRunArg:
    """Tests for --run argument parsing."""

    def test_run_default_is_false(self):
        """--run should default to False."""
        args = parse_args(["."])
        assert args.run_sim is False

    def test_run_flag(self):
        """--run should set run_sim to True."""
        args = parse_args(["--run", "."])
        assert args.run_sim is True

    def test_run_via_r(self):
        """-r should set run_sim to True."""
        args = parse_args([".", "-r"])
        assert args.run_sim is True

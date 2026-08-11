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


class TestCleanArg:
    """Tests for --clean argument parsing."""

    def test_clean_without_value_defaults_to_outputs(self):
        """--clean without value should default to 'outputs'."""
        args = parse_args([".", "--clean"])
        assert args.clean == "outputs"

    def test_clean_all(self):
        """--clean all should be accepted."""
        args = parse_args([".", "--clean", "all"])
        assert args.clean == "all"

    def test_clean_outputs(self):
        """--clean outputs should be accepted."""
        args = parse_args([".", "--clean", "outputs"])
        assert args.clean == "outputs"

    def test_clean_default_is_none(self):
        """Default should be None (not set)."""
        args = parse_args(["."])
        assert args.clean is None

    def test_clean_invalid_rejected(self):
        """--clean with an unexpected value should be rejected."""
        with pytest.raises(SystemExit):
            parse_args([".", "--clean", "foo"])


class TestMakeArg:
    """Tests for --make argument parsing."""

    def test_make_bare(self):
        """Bare --make should default to empty options."""
        args = parse_args([".", "--make"])
        assert args.make == ""

    def test_make_opts(self):
        """--make should accept comma-separated known options."""
        args = parse_args([".", "--make", "clean,large"])
        assert args.make == "clean,large"

    def test_make_invalid_rejected(self):
        """--make with an unexpected option should be rejected."""
        with pytest.raises(SystemExit):
            parse_args([".", "--make", "path/to/sim"])


class TestMainPrecedence:
    """Tests for linear compile -> clean -> run chaining in main()."""

    @staticmethod
    def _run(argv, tmp_path, monkeypatch, moccarun_module):
        order = []
        monkeypatch.setattr(moccarun_module, "find_mocca_src_path", lambda p: tmp_path)
        monkeypatch.setattr(moccarun_module, "make_mocca", lambda *a, **k: order.append("make"))
        monkeypatch.setattr(moccarun_module, "clean_dir", lambda *a, **k: order.append("clean"))
        monkeypatch.setattr(moccarun_module, "moccarun", lambda *a, **k: order.append("run"))
        monkeypatch.setattr(moccarun_module, "verify_cleaned", lambda *a, **k: True)
        monkeypatch.setattr("sys.argv", ["mrun", *argv])
        moccarun_module.main()
        return order

    def test_make_clean_run_order(self, tmp_path, monkeypatch):
        """--make --clean --run should chain compile -> clean -> run."""
        import moccarun

        sim = str(tmp_path / "sim")
        (tmp_path / "sim").mkdir()
        order = self._run([sim, "--make", "--clean", "--run"], tmp_path, monkeypatch, moccarun)
        assert order == ["make", "clean", "run"]

    def test_default_only_runs(self, tmp_path, monkeypatch):
        """No flags should still run moccarun (dry-run prep)."""
        import moccarun

        sim = str(tmp_path / "sim")
        (tmp_path / "sim").mkdir()
        order = self._run([sim], tmp_path, monkeypatch, moccarun)
        assert order == ["run"]

    def test_make_only_compiles_then_runs(self, tmp_path, monkeypatch):
        """--make alone should compile then run, without cleaning."""
        import moccarun

        sim = str(tmp_path / "sim")
        (tmp_path / "sim").mkdir()
        order = self._run([sim, "--make"], tmp_path, monkeypatch, moccarun)
        assert order == ["make", "run"]

    def test_clean_only_cleans_then_runs(self, tmp_path, monkeypatch):
        """--clean alone should clean then run, without compiling."""
        import moccarun

        sim = str(tmp_path / "sim")
        (tmp_path / "sim").mkdir()
        order = self._run([sim, "--clean", "all"], tmp_path, monkeypatch, moccarun)
        assert order == ["clean", "run"]


class TestVerifyCleaned:
    """Tests for verify_cleaned() post-condition check."""

    def test_no_leftover_files(self, tmp_path):
        """Only keep files present -> True."""
        import moccarun

        (tmp_path / "mocca.ini").write_text("")
        (tmp_path / "mocca.slurm").write_text("")
        assert moccarun.verify_cleaned(tmp_path, ["mocca.ini", "mocca.slurm"]) is True

    def test_leftover_files_fail(self, tmp_path):
        """Extra files remain -> False."""
        import moccarun

        (tmp_path / "mocca.ini").write_text("")
        (tmp_path / "stale_output.log").write_text("")
        assert moccarun.verify_cleaned(tmp_path, ["mocca.ini"]) is False

    def test_empty_dir_ok(self, tmp_path):
        """Empty dir has no leftovers -> True."""
        import moccarun

        assert moccarun.verify_cleaned(tmp_path, ["mocca.ini"]) is True


class _FakeProc:
    def __init__(self, returncode=0):
        self.returncode = returncode


class TestMakeMocca:
    """Tests for make_mocca() return-code and fresh-binary verification."""

    @staticmethod
    def _setup(tmp_path, monkeypatch):
        import moccarun

        src = tmp_path / "src"
        src.mkdir()
        return moccarun, src

    def test_compile_failure_exits(self, tmp_path, monkeypatch):
        """Non-zero make return code -> exit."""
        import moccarun

        moccarun, src = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(1))
        with pytest.raises(SystemExit):
            moccarun.make_mocca(src, opts=["clean"])

    def test_missing_binary_exits(self, tmp_path, monkeypatch):
        """make returned 0 but no binary -> exit."""
        import moccarun

        moccarun, src = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(0))
        with pytest.raises(SystemExit):
            moccarun.make_mocca(src, opts=["clean"])

    def test_stale_binary_exits(self, tmp_path, monkeypatch):
        """Pre-existing binary not rebuilt after 'make clean' -> exit."""
        import moccarun

        moccarun, src = self._setup(tmp_path, monkeypatch)
        (src / "mocca").write_text("")  # pre-existing, stale (before t0)
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(0))
        with pytest.raises(SystemExit):
            moccarun.make_mocca(src, opts=["clean"])

    def test_fresh_binary_ok(self, tmp_path, monkeypatch):
        """Binary created during make -> no error."""
        import moccarun

        moccarun, src = self._setup(tmp_path, monkeypatch)

        def fake_run(cmd, **k):
            (src / "mocca").write_text("binary")  # built during make (after t0)
            return _FakeProc(0)

        monkeypatch.setattr(moccarun, "run", fake_run)
        moccarun.make_mocca(src, opts=["clean"])  # no exception


class TestVerifyShortCircuit:
    """Tests that verification failure skips later steps."""

    def test_clean_verify_failure_skips_run(self, tmp_path, monkeypatch):
        """--clean with leftover files should skip moccarun."""
        import moccarun

        sim = str(tmp_path / "sim")
        (tmp_path / "sim").mkdir()
        order = []
        monkeypatch.setattr(moccarun, "find_mocca_src_path", lambda p: tmp_path)
        monkeypatch.setattr(moccarun, "make_mocca", lambda *a, **k: order.append("make"))
        monkeypatch.setattr(moccarun, "clean_dir", lambda *a, **k: order.append("clean"))
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: order.append("run"))
        monkeypatch.setattr(moccarun, "verify_cleaned", lambda *a, **k: False)
        monkeypatch.setattr("sys.argv", ["mrun", sim, "--clean", "all"])
        moccarun.main()
        assert order == ["clean"]


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

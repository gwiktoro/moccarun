import pytest

import moccarun
from moccarun import parse_args


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_grid_accepts_json_string(self):
        args = parse_args(["--grid", '{"n": [1, 2]}', "."])
        assert args.grid == '{"n": [1, 2]}'

    def test_moccaini_parses_json(self):
        args = parse_args(["--moccaini", '{"n": 100}', "."])
        assert args.moccaini == {"n": 100}

    @pytest.mark.parametrize("partition", ["short", "long", "bigmem"])
    def test_partition(self, partition):
        assert parse_args(["--partition", partition, "."]).partition == partition
        assert parse_args(["-p", partition, "."]).partition == partition

    def test_partition_invalid_rejected(self):
        with pytest.raises(SystemExit):
            parse_args(["--partition", "invalid", "."])

    def test_log_level(self):
        assert parse_args(["."]).logLevel == "INFO"
        assert parse_args(["--logLevel", "DEBUG", "."]).logLevel == "DEBUG"

    def test_version_flag_accepted(self):
        assert parse_args(["--version"]).version is True

    def test_no_slurm_flag(self):
        assert parse_args(["--no-slurm", "."]).no_slurm is True

    def test_default_paths_is_current_dir(self):
        from pathlib import Path

        assert parse_args([]).paths == [Path(".")]

    def test_multiple_paths_accepted(self):
        assert len(parse_args(["path1", "path2", "path3"]).paths) == 3

    @pytest.mark.parametrize("flag", ["--dry-run", "--moccainipath=x"])
    def test_removed_flags_rejected(self, flag):
        with pytest.raises(SystemExit):
            parse_args([flag, "."])

    def test_mocca_paths_options(self):
        from pathlib import Path

        args = parse_args([".", "--mocca-src", "a", "--mocca-binary", "b", "--from", "c", "--keep-mocca-binary"])
        assert (args.mocca_src, args.mocca_binary, args.ref_dir) == (Path("a"), Path("b"), Path("c"))
        assert args.keep_mocca_binary is True

    def test_keep_mocca_binary_default_false(self):
        assert parse_args(["."]).keep_mocca_binary is False

    def test_keep_mocca_binary_short_flag(self):
        assert parse_args(["-k", "."]).keep_mocca_binary is True



class TestCleanArg:
    def test_clean_without_value_defaults_to_outputs(self):
        assert parse_args([".", "--clean"]).clean == "outputs"

    @pytest.mark.parametrize("mode", ["all", "outputs"])
    def test_clean_modes(self, mode):
        assert parse_args([".", "--clean", mode]).clean == mode

    def test_clean_default_is_none(self):
        assert parse_args(["."]).clean is None

    def test_clean_invalid_rejected(self):
        with pytest.raises(SystemExit):
            parse_args([".", "--clean", "foo"])


class TestMakeArg:
    def test_make_bare(self):
        assert parse_args([".", "--make"]).make == ""

    def test_make_opts(self):
        assert parse_args([".", "--make", "clean,large"]).make == "clean,large"

    @pytest.mark.parametrize("bad", ["path/to/sim", "find"])
    def test_make_invalid_rejected(self, bad):
        with pytest.raises(SystemExit):
            parse_args([".", "--make", bad])


class TestRunArg:
    def test_run_default_is_false(self):
        assert parse_args(["."]).run_sim is False

    @pytest.mark.parametrize("flag", ["--run", "-r"])
    def test_run_flag(self, flag):
        assert parse_args([flag, "."]).run_sim is True


class TestMainChaining:
    """main() chains: compile once -> per path: clean -> prepare/run."""

    @staticmethod
    def _run(argv, monkeypatch):
        order = []
        monkeypatch.setattr(moccarun, "resolve_mocca_src", lambda *a, **k: "src")
        monkeypatch.setattr(moccarun, "get_user_email", lambda e=None: "me@example.org")
        monkeypatch.setattr(moccarun, "make_mocca", lambda *a, **k: order.append("make"))
        monkeypatch.setattr(moccarun, "clean_dir", lambda *a, **k: order.append("clean"))
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: order.append("run"))
        assert moccarun.main(argv) == 0
        return order

    def test_make_clean_run_order(self, tmp_path, monkeypatch):
        assert self._run([str(tmp_path), "--make", "--clean", "--run"], monkeypatch) == [
            "make", "clean", "run"
        ]

    def test_default_only_prepares(self, tmp_path, monkeypatch):
        assert self._run([str(tmp_path)], monkeypatch) == ["run"]

    def test_make_then_run(self, tmp_path, monkeypatch):
        assert self._run([str(tmp_path), "--make"], monkeypatch) == ["make", "run"]

    def test_clean_then_run(self, tmp_path, monkeypatch):
        assert self._run([str(tmp_path), "--clean", "all"], monkeypatch) == ["clean", "run"]

    def test_clean_skips_missing_dir(self, tmp_path, monkeypatch):
        assert self._run([str(tmp_path / "new"), "--clean"], monkeypatch) == ["run"]

    def test_make_once_for_many_paths(self, tmp_path, monkeypatch):
        order = self._run([str(tmp_path / "a"), str(tmp_path / "b"), "--make"], monkeypatch)
        assert order == ["make", "run", "run"]

    def test_grid_expands_paths_and_ini(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(moccarun, "get_user_email", lambda e=None: "me@example.org")
        monkeypatch.setattr(moccarun, "moccarun", lambda path, *a, **k: calls.append((path.name, k["moccaini"])))
        argv = [str(tmp_path), "--grid", '{"n": [1, 2], "w0": [3]}', "--moccaini", '{"fracb": 0.5}']
        assert moccarun.main(argv) == 0
        assert calls == [
            ("n=1_w0=3", {"fracb": 0.5, "n": 1, "w0": 3}),
            ("n=2_w0=3", {"fracb": 0.5, "n": 2, "w0": 3}),
        ]

    def test_grid_needs_single_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(moccarun, "get_user_email", lambda e=None: "me@example.org")
        assert moccarun.main(["a", "b", "--grid", "{}"]) == 1

    def test_error_returns_nonzero(self, tmp_path, monkeypatch):
        def fail(*a, **k):
            raise moccarun.MoccaError("boom")

        monkeypatch.setattr(moccarun, "get_user_email", lambda e=None: "me@example.org")
        monkeypatch.setattr(moccarun, "moccarun", fail)
        assert moccarun.main([str(tmp_path)]) == 1


class TestCleanDir:
    def test_removes_all_but_kept(self, tmp_path):
        (tmp_path / "mocca.ini").write_text("")
        (tmp_path / "out.dat").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "x").write_text("")
        moccarun.clean_dir(tmp_path, keep=["mocca.ini"])
        assert [p.name for p in tmp_path.iterdir()] == ["mocca.ini"]


class _FakeProc:
    def __init__(self, returncode=0):
        self.returncode = returncode


class TestMakeMocca:
    """Tests for make_mocca() return-code and fresh-binary verification."""

    def test_compile_failure_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(1))
        with pytest.raises(moccarun.MoccaError):
            moccarun.make_mocca(tmp_path, opts=["clean"])

    def test_missing_binary_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(0))
        with pytest.raises(moccarun.MoccaError):
            moccarun.make_mocca(tmp_path, opts=["clean"])

    def test_stale_binary_exits(self, tmp_path, monkeypatch):
        (tmp_path / "mocca").write_text("")
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: _FakeProc(0))
        with pytest.raises(moccarun.MoccaError):
            moccarun.make_mocca(tmp_path, opts=["clean"])

    def test_fresh_binary_ok(self, tmp_path, monkeypatch):
        def fake_run(cmd, **k):
            (tmp_path / "mocca").write_text("binary")
            return _FakeProc(0)

        monkeypatch.setattr(moccarun, "run", fake_run)
        moccarun.make_mocca(tmp_path, opts=["clean"])

    def test_make_commands_run_in_src(self, tmp_path, monkeypatch):
        calls = []

        def fake_run(cmd, **k):
            calls.append((cmd, k["cwd"]))
            (tmp_path / "mocca").write_text("binary")
            return _FakeProc(0)

        monkeypatch.setattr(moccarun, "run", fake_run)
        moccarun.make_mocca(tmp_path, opts=["clean"])
        assert calls == [(["make", "clean"], tmp_path), (["make", "debug"], tmp_path)]

    def test_size_edits_params_h(self, tmp_path, monkeypatch):
        (tmp_path / "MOCCA").mkdir()
        params = tmp_path / "MOCCA" / "params.h"
        params.write_text("      PARAMETER (NMAX=3276007,NBMAX3=1596002,NZONMA=20100,NSUPZO=400)\n")

        def fake_run(cmd, **k):
            (tmp_path / "mocca").write_text("binary")
            return _FakeProc(0)

        monkeypatch.setattr(moccarun, "run", fake_run)
        moccarun.make_mocca(tmp_path, opts=["large"])
        assert params.read_text() == (
            "      PARAMETER (NMAX=5200000,NBMAX3=5200000,NZONMA=20100,NSUPZO=600)\n"
        )

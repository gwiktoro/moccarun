"""Nothing happens, is skipped or is rejected without the user being told."""

import subprocess

import pytest
from loguru import logger

import moccarun

from .conftest import has

EMAIL = "me@example.org"


def prep(path, **kw):
    kw.setdefault("user_email", EMAIL)
    moccarun.moccarun(path, **kw)


def fake_run(monkeypatch, **results):
    """sbatch / ./mocca / make return the given exit codes; other commands run for real"""
    real = moccarun.run

    def run(cmd, **k):
        name = cmd[0].lstrip("./")
        if name in results:
            return subprocess.CompletedProcess(cmd, results[name], stdout=b"out", stderr=b"boom")
        return real(cmd, **k)

    monkeypatch.setattr(moccarun, "run", run)


class TestDefaults:
    def test_default_level_shows_actions(self):
        assert moccarun.parse_args(["."]).logLevel == "INFO"

    def test_format_is_compact(self, capsys):
        moccarun.setup_logging("INFO")
        logger.info("hello")
        err = capsys.readouterr().err
        assert err.strip().endswith("hello") and "INFO" in err and "20" not in err.split("INFO")[0]


class TestPrepareIsReported:
    def test_new_directory_run(self, project, log):
        prep(project.runs / "sim", partition="short", moccaini={"n": 7})
        for text in (
            "creating directory",
            "using MOCCA src",
            "creating",  # configs
            "copying binary",
            "n = 7",
            "runmaxcpu",
            "#SBATCH -J sim",
            "--mail-user",
            "#SBATCH -p short",
            "not started",
        ):
            assert has(log, "INFO", text), (text, log)

    def test_existing_configs_kept_visibly(self, project, log):
        prep(project.runs / "sim")
        log.clear()
        prep(project.runs / "sim")
        assert has(log, "INFO", "keeping existing") and has(log, "INFO", "--from")
        assert not has(log, "INFO", "creating directory")

    def test_from_overwrite_reported(self, project, tmp_path, log):
        ref = tmp_path / "ref"
        ref.mkdir()
        (ref / "mocca.ini").write_text("[A]\nn = 5\n")
        (ref / "mocca.slurm").write_text("#SBATCH -J r\n./mocca > zzz\n")
        prep(project.runs / "sim", ref_dir=ref)
        log.clear()
        prep(project.runs / "sim", ref_dir=ref)
        assert has(log, "INFO", "(overwriting)")

    def test_keep_binary_reported(self, project, log):
        sim = project.runs / "sim"
        prep(sim)
        log.clear()
        prep(sim, keep_mocca_binary=True)
        assert has(log, "INFO", "keeping existing binary")
        assert not has(log, "INFO", "copying binary")

    def test_keep_binary_but_none_present_warns(self, project, log):
        prep(project.runs / "sim", keep_mocca_binary=True)
        assert has(log, "WARNING", "--keep-mocca-binary")

    def test_slurm_line_not_found_warns(self, project, log):
        (project.src / "mocca.slurm").write_text("#!/bin/bash\n./mocca > zzz\n")
        prep(project.runs / "sim", partition="short")
        assert has(log, "WARNING", "nothing to update")

    def test_email_source_reported(self, log):
        moccarun.get_user_email("a@b.c")
        assert has(log, "INFO", "a@b.c") and has(log, "INFO", "--user-email")

    def test_email_fallback_warns(self, monkeypatch, log):
        monkeypatch.setattr(moccarun, "git_user_email", lambda: None)
        monkeypatch.delenv("MOCCARUN_EMAIL", raising=False)
        monkeypatch.setenv("EMAIL", "sys@example.org")
        assert moccarun.get_user_email() == "sys@example.org"
        assert has(log, "WARNING", "no email in git config") and has(log, "INFO", "(EMAIL)")


class TestRunIsReported:
    def test_submit(self, project, monkeypatch, log):
        fake_run(monkeypatch, sbatch=0)
        prep(project.runs / "sim", run_sim=True, wait=True)
        assert has(log, "INFO", "submitting: sbatch --wait mocca.slurm")

    def test_submit_failure_has_reason(self, project, monkeypatch):
        fake_run(monkeypatch, sbatch=1)
        with pytest.raises(moccarun.MoccaError, match="boom"):
            prep(project.runs / "sim", run_sim=True)

    def test_local_run_reported(self, project, monkeypatch, log):
        fake_run(monkeypatch, mocca=0)
        prep(project.runs / "sim", run_sim=True, no_slurm=True)
        assert has(log, "INFO", "locally") and has(log, "INFO", "local run finished")

    def test_local_run_failure_not_ignored(self, project, monkeypatch):
        fake_run(monkeypatch, mocca=3)
        with pytest.raises(moccarun.MoccaError, match="exit code 3"):
            prep(project.runs / "sim", run_sim=True, no_slurm=True)


class TestMakeAndClean:
    def test_clean_announces_removal(self, tmp_path, log):
        (tmp_path / "mocca.ini").write_text("")
        (tmp_path / "a.dat").write_text("")
        (tmp_path / "b.dat").write_text("")
        moccarun.clean_dir(tmp_path, keep=["mocca.ini"])
        assert has(log, "WARNING", "removing 2 item(s)")

    def test_make_steps_reported(self, tmp_path, monkeypatch, log):
        (tmp_path / "MOCCA").mkdir()
        (tmp_path / "MOCCA" / "params.h").write_text("NMAX=1,NBMAX3=1,NSUPZO=1")

        def run(cmd, **k):
            (tmp_path / "mocca").write_text("b")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(moccarun, "run", run)
        moccarun.make_mocca(tmp_path, opts=["clean", "large"])
        for text in ("NMAX=5200000", "make clean", "make debug", "compiled"):
            assert has(log, "INFO", text), (text, log)

    def test_params_h_key_missing_warns(self, tmp_path, monkeypatch, log):
        (tmp_path / "MOCCA").mkdir()
        (tmp_path / "MOCCA" / "params.h").write_text("nothing here")
        monkeypatch.setattr(moccarun, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0))
        with pytest.raises(moccarun.MoccaError):  # no binary produced
            moccarun.make_mocca(tmp_path, opts=["large"])
        assert has(log, "WARNING", "NMAX not found")


class TestMainReportsEverything:
    @staticmethod
    def _main(argv, monkeypatch):
        monkeypatch.setattr(moccarun, "get_user_email", lambda e=None: EMAIL)
        return moccarun.main(argv)

    def test_failed_path_does_not_hide_others(self, tmp_path, monkeypatch, log):
        calls = []

        def fake(path, *a, **k):
            calls.append(path.name)
            if path.name == "bad":
                raise moccarun.MoccaError("rejected")

        monkeypatch.setattr(moccarun, "moccarun", fake)
        rc = self._main([str(tmp_path / "bad"), str(tmp_path / "good")], monkeypatch)
        assert rc == 1 and calls == ["bad", "good"]
        assert has(log, "ERROR", "rejected") and has(log, "ERROR", "failed:")
        assert has(log, "INFO", "1/2 simulation(s)")

    def test_success_summary(self, tmp_path, monkeypatch, log):
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: None)
        assert self._main([str(tmp_path / "a")], monkeypatch) == 0
        assert has(log, "INFO", "1/1 simulation(s) prepared, not started")

    def test_run_summary(self, tmp_path, monkeypatch, log):
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: None)
        self._main([str(tmp_path / "a"), "--run"], monkeypatch)
        assert has(log, "INFO", "1/1 simulation(s) started")

    def test_clean_of_missing_dir_reported(self, tmp_path, monkeypatch, log):
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: None)
        self._main([str(tmp_path / "new"), "--clean"], monkeypatch)
        assert has(log, "INFO", "nothing to clean")

    def test_bad_grid_json_is_an_error_not_a_traceback(self, tmp_path, monkeypatch, log):
        assert self._main([str(tmp_path), "--grid", "{not json"], monkeypatch) == 1
        assert has(log, "ERROR", "--grid")

    def test_grid_size_reported(self, tmp_path, monkeypatch, log):
        monkeypatch.setattr(moccarun, "moccarun", lambda *a, **k: None)
        self._main([str(tmp_path), "--grid", '{"n": [1, 2, 3]}'], monkeypatch)
        assert has(log, "INFO", "grid: 3 simulation(s)")

    def test_os_error_is_reported(self, project, monkeypatch, log):
        def run(cmd, **k):
            raise FileNotFoundError(2, "No such file or directory", "sbatch")

        monkeypatch.setattr(moccarun, "run", run)
        monkeypatch.setattr(moccarun, "resolve_mocca_src", lambda *a, **k: project.src)
        rc = self._main([str(project.runs / "sim"), "--run"], monkeypatch)
        assert rc == 1 and has(log, "ERROR", "sbatch")

    def test_not_in_mocca_repo_is_an_error(self, tmp_path, monkeypatch, log):
        assert self._main([str(tmp_path / "sim")], monkeypatch) == 1
        assert has(log, "ERROR", "git repository")

    def test_grep_without_matches_warns(self, project, monkeypatch, log):
        (project.src / "MOCCA" / "montcarl.f").write_text("      call foo\n")
        monkeypatch.chdir(project.root)
        assert self._main(["--grep", "zzzzz", str(project.root)], monkeypatch) == 0
        assert has(log, "WARNING", "no matches")

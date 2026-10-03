import subprocess

import pytest

import moccarun

EMAIL = "me@example.org"


def prep(path, **kw):
    kw.setdefault("user_email", EMAIL)
    moccarun.moccarun(path, **kw)


@pytest.fixture
def calls(monkeypatch):
    """record every command; sbatch and ./mocca are faked, everything else (git) runs"""
    recorded = []
    real = moccarun.run

    def spy(cmd, **k):
        recorded.append(cmd)
        if cmd[0] in ("sbatch", "./mocca"):
            return subprocess.CompletedProcess(cmd, 0, stdout=b"Submitted batch job 1", stderr=b"")
        return real(cmd, **k)

    monkeypatch.setattr(moccarun, "run", spy)
    return recorded


class TestDefaultPrepare:
    def test_new_dir_gets_defaults_and_binary(self, project):
        sim = project.runs / "sim"
        prep(sim)
        assert (sim / "mocca").read_text() == "binary"
        assert "n = 1000, 500" in (sim / "mocca.ini").read_text()
        assert (sim / "mocca.slurm").is_file()

    def test_slurm_job_name_mail_and_command(self, project):
        sim = project.runs / "sim"
        prep(sim)
        slurm = (sim / "mocca.slurm").read_text()
        assert "#SBATCH -J sim\n" in slurm
        assert f"\n#SBATCH --mail-user={EMAIL}\n" in slurm  # was commented out (##) in the template
        assert "\n./mocca > zzz\n" in slurm

    def test_slurm_without_partition_keeps_template_limits(self, project):
        sim = project.runs / "sim"
        prep(sim)
        slurm = (sim / "mocca.slurm").read_text()
        assert "--time=336:00:00" in slurm and "-p long" in slurm
        assert "runmaxcpu = 0" in (sim / "mocca.ini").read_text()

    @pytest.mark.parametrize(
        "partition, time, mem, runmaxcpu",
        [("short", "36:00:00", "2999MB", 1944), ("long", "336:00:00", "2999MB", 18144), ("bigmem", "168:00:00", "5999MB", 9072)],
    )
    def test_partition(self, project, partition, time, mem, runmaxcpu):
        sim = project.runs / "sim"
        prep(sim, partition=partition)
        slurm = (sim / "mocca.slurm").read_text()
        assert f"#SBATCH --time={time}\n" in slurm
        assert f"#SBATCH --mem-per-cpu={mem}\n" in slurm
        assert f"#SBATCH -p {partition}\n" in slurm
        assert f"runmaxcpu = {runmaxcpu}\n" in (sim / "mocca.ini").read_text()

    def test_explicit_runmaxcpu_wins_over_partition(self, project):
        sim = project.runs / "sim"
        prep(sim, partition="short", moccaini={"runmaxcpu": 5})
        assert "runmaxcpu = 5\n" in (sim / "mocca.ini").read_text()

    def test_escape_bin_restart(self, project):
        sim = project.runs / "sim"
        prep(sim, escape_bin_restart=True)
        assert "./mocca --escape-bin-restart > zzz-escape-bin-restart" in (sim / "mocca.slurm").read_text()

    def test_moccaini_keeps_comments_and_edits_only_active_key(self, project):
        sim = project.runs / "sim"
        prep(sim, moccaini={"n": 7, "fracb": 0.5})
        ini = (sim / "mocca.ini").read_text()
        assert "n = 7\n" in ini and "fracb = 0.5\n" in ini
        assert "# fracb = 0.1\n" in ini and "# comment about n\n" in ini

    def test_moccaini_unknown_key(self, project):
        with pytest.raises(moccarun.MoccaError, match="nokey"):
            prep(project.runs / "sim", moccaini={"nokey": 1})

    def test_moccaini_commented_key_not_editable(self, project):
        (project.src / "mocca-default-2pop.ini").write_text("# only = 1\n")
        with pytest.raises(moccarun.MoccaError):
            prep(project.runs / "sim", moccaini={"only": 2})


class TestExistingConfigs:
    def test_existing_configs_untouched(self, project):
        sim = project.runs / "sim"
        sim.mkdir(parents=True)
        (sim / "mocca.ini").write_text("[A]\nmine = 1\n")
        (sim / "mocca.slurm").write_text("#SBATCH -J x\n./mocca > zzz\n")
        prep(sim)
        assert (sim / "mocca.ini").read_text() == "[A]\nmine = 1\n"
        assert "#SBATCH -J sim\n" in (sim / "mocca.slurm").read_text()  # patched, not replaced

    def test_only_missing_file_created(self, project):
        sim = project.runs / "sim"
        sim.mkdir(parents=True)
        (sim / "mocca.ini").write_text("[A]\nmine = 1\n")
        prep(sim)
        assert (sim / "mocca.ini").read_text() == "[A]\nmine = 1\n"
        assert (sim / "mocca.slurm").is_file()

    def test_updates_apply_to_existing_config(self, project):
        sim = project.runs / "sim"
        prep(sim)
        prep(sim, moccaini={"n": 3}, partition="short")
        ini = (sim / "mocca.ini").read_text()
        assert "n = 3\n" in ini and "runmaxcpu = 1944\n" in ini


class TestFrom:
    @pytest.fixture
    def ref(self, tmp_path):
        ref = tmp_path / "ref"
        ref.mkdir()
        (ref / "mocca.ini").write_text("[A]\nn = 5\n")
        (ref / "mocca.slurm").write_text("#SBATCH -J r\n./mocca > zzz\n")
        (ref / "binary_nbody.dat").write_text("b")
        (ref / "single_nbody.dat").write_text("s")
        (ref / "mocca").write_text("REF BINARY")
        return ref

    def test_overwrites_existing_and_copies_nbody(self, project, ref):
        sim = project.runs / "sim"
        sim.mkdir(parents=True)
        (sim / "mocca.ini").write_text("[A]\nn = 1\n")
        prep(sim, ref_dir=ref)
        assert (sim / "mocca.ini").read_text() == "[A]\nn = 5\n"
        assert (sim / "binary_nbody.dat").read_text() == "b"
        assert (sim / "single_nbody.dat").read_text() == "s"

    def test_binary_never_from_ref(self, project, ref):
        sim = project.runs / "sim"
        prep(sim, ref_dir=ref)
        assert (sim / "mocca").read_text() == "binary"  # from mocca/src

    def test_keep_binary_with_from_copies_no_binary(self, project, ref):
        sim = project.runs / "sim"
        prep(sim, ref_dir=ref, keep_mocca_binary=True)
        assert not (sim / "mocca").exists()

    def test_ref_without_configs(self, project, tmp_path):
        with pytest.raises(moccarun.MoccaError, match="--from"):
            prep(project.runs / "sim", ref_dir=tmp_path)

    def test_from_needs_no_mocca_src_when_keeping_binary(self, tmp_path, ref):
        """no git/MOCCA lookup at all when nothing is taken from MOCCA's src/"""
        sim = tmp_path / "sim"
        prep(sim, ref_dir=ref, keep_mocca_binary=True)
        assert (sim / "mocca.ini").is_file()


class TestBinary:
    def test_keep_mocca_binary_leaves_existing_binary(self, project):
        sim = project.runs / "sim"
        sim.mkdir(parents=True)
        (sim / "mocca").write_text("old")
        prep(sim, keep_mocca_binary=True)
        assert (sim / "mocca").read_text() == "old"

    def test_default_overwrites_existing_binary(self, project):
        sim = project.runs / "sim"
        sim.mkdir(parents=True)
        (sim / "mocca").write_text("old")
        prep(sim)
        assert (sim / "mocca").read_text() == "binary"

    def test_binary_picked_up_after_recompile(self, project):
        sim = project.runs / "sim"
        prep(sim)
        (project.src / "mocca").write_text("rebuilt")
        prep(sim)
        assert (sim / "mocca").read_text() == "rebuilt"

    def test_mocca_binary_override(self, project, tmp_path):
        custom = tmp_path / "custom_mocca"
        custom.write_text("custom")
        sim = project.runs / "sim"
        prep(sim, mocca_binary=custom)
        assert (sim / "mocca").read_text() == "custom"

    def test_mocca_src_override_for_defaults_and_binary(self, tmp_path, project):
        from .conftest import make_mocca_repo

        other = tmp_path / "other_mocca"
        other.mkdir()
        other_src = make_mocca_repo(other)
        (other_src / "mocca").write_text("other binary")
        sim = tmp_path / "elsewhere" / "sim"  # not inside any git repo
        prep(sim, mocca_src=other_src)
        assert (sim / "mocca").read_text() == "other binary"

    def test_missing_binary_in_src(self, project):
        (project.src / "mocca").unlink()
        with pytest.raises(moccarun.MoccaError, match="binary not found"):
            prep(project.runs / "sim")


class TestNoSubmitWithoutRun:
    def test_no_sbatch_by_default(self, project, calls):
        prep(project.runs / "sim")
        assert not any(c[0] in ("sbatch", "./mocca") for c in calls)

    def test_no_slurm_without_run_does_nothing(self, project, calls):
        prep(project.runs / "sim", no_slurm=True, wait=True)
        assert not any(c[0] in ("sbatch", "./mocca") for c in calls)

    def test_run_submits(self, project, calls):
        prep(project.runs / "sim", run_sim=True)
        assert ["sbatch", "mocca.slurm"] in calls

    def test_run_wait(self, project, calls):
        prep(project.runs / "sim", run_sim=True, wait=True)
        assert ["sbatch", "--wait", "mocca.slurm"] in calls

    def test_run_local(self, project, calls):
        prep(project.runs / "sim", run_sim=True, no_slurm=True)
        assert ["./mocca"] in calls and not any(c[0] == "sbatch" for c in calls)

    def test_run_without_binary_fails(self, project, calls):
        with pytest.raises(moccarun.MoccaError, match="no mocca binary"):
            prep(project.runs / "sim", run_sim=True, keep_mocca_binary=True)

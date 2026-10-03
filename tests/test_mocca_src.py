import pytest

import moccarun
from .conftest import git, make_mocca_repo


class TestFindMoccaSrc:
    def test_finds_mocca_src_in_git_root(self, project):
        assert moccarun.find_mocca_src_path(project.root) == project.src

    def test_path_need_not_exist(self, project):
        assert moccarun.find_mocca_src_path(project.runs / "new" / "sim") == project.src

    def test_uses_path_not_cwd(self, project, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert moccarun.find_mocca_src_path(project.runs) == project.src

    def test_not_in_git_repo(self, tmp_path):
        with pytest.raises(moccarun.MoccaError, match="not in a git repository"):
            moccarun.find_mocca_src_path(tmp_path)

    def test_standalone_mocca_repo(self, tmp_path):
        """<git-root>/src works when the git repo is MOCCA itself"""
        src = make_mocca_repo(tmp_path)
        assert moccarun.find_mocca_src_path(tmp_path / "src" / "run" / "sim") == src

    def test_mocca_src_takes_precedence_over_src(self, tmp_path):
        """both valid: <git-root>/mocca/src wins over <git-root>/src"""
        outer_src = make_mocca_repo(tmp_path)  # git root with a valid src/ ...
        inner_src = make_mocca_repo(tmp_path / "mocca")  # ... and a nested valid mocca/src
        assert moccarun.validate_mocca_src(outer_src) == outer_src
        assert moccarun.find_mocca_src_path(tmp_path) == inner_src

    def test_falls_back_to_src_when_mocca_src_invalid(self, tmp_path):
        """<git-root>/mocca/src exists but is not MOCCA -> use <git-root>/src"""
        src = make_mocca_repo(tmp_path)
        (tmp_path / "mocca" / "src").mkdir(parents=True)
        assert moccarun.find_mocca_src_path(tmp_path) == src

    def test_uninitialized_submodule_rejected(self, tmp_path):
        """empty mocca/ inside another repo: its git root is the parent repo"""
        git(tmp_path, "init", "-q")
        (tmp_path / "mocca" / "src").mkdir(parents=True)
        with pytest.raises(moccarun.MoccaError, match="uninitialized submodule"):
            moccarun.find_mocca_src_path(tmp_path)

    def test_error_lists_all_candidates(self, tmp_path):
        git(tmp_path, "init", "-q")
        (tmp_path / "src").mkdir()
        with pytest.raises(moccarun.MoccaError) as e:
            moccarun.find_mocca_src_path(tmp_path)
        assert str(tmp_path / "mocca" / "src") in str(e.value) and str(tmp_path / "src") in str(e.value)


class TestValidateMoccaSrc:
    def test_valid(self, project):
        assert moccarun.validate_mocca_src(project.src) == project.src

    @pytest.mark.parametrize(
        "remote",
        [
            "git@gitlab.camk.edu.pl:mocca/mocca.git",
            "https://example.org/someone/mocca",
            "https://example.org/someone/mocca/",
            "/local/path/to/mocca.git",
            "mocca",
        ],
    )
    def test_remote_name_forms(self, tmp_path, remote):
        src = make_mocca_repo(tmp_path, remote=remote)
        assert moccarun.validate_mocca_src(src) == src

    def test_second_remote_named_mocca(self, tmp_path):
        src = make_mocca_repo(tmp_path, remote="git@example.org:me/other.git")
        git(tmp_path, "remote", "add", "upstream", "git@example.org:mocca/mocca.git")
        assert moccarun.validate_mocca_src(src) == src

    @pytest.mark.parametrize("remote", ["git@example.org:me/moccarun.git", "git@example.org:mocca/other.git", None])
    def test_other_repo_name_rejected(self, tmp_path, remote):
        """right files, wrong repository (folder named mocca is not enough)"""
        root = tmp_path / "mocca"  # folder name is irrelevant
        root.mkdir()
        src = make_mocca_repo(root, remote=remote)
        with pytest.raises(moccarun.MoccaError, match="not the MOCCA repository"):
            moccarun.validate_mocca_src(src)

    @pytest.mark.parametrize("name", ["mocca-default-2pop.ini", "mocca.slurm", "makefile", "MOCCA/montcarl.f", "bse"])
    def test_missing_tracked_files_rejected(self, project, name):
        import shutil

        target = project.src / name
        shutil.rmtree(target) if target.is_dir() else target.unlink()
        git(project.src.parent, "add", "-A")
        git(project.src.parent, "commit", "-q", "-m", "rm")
        with pytest.raises(moccarun.MoccaError, match="not tracked by git"):
            moccarun.validate_mocca_src(project.src)

    def test_untracked_files_do_not_count(self, tmp_path):
        """MOCCA-like files that exist but are not tracked by git: not a MOCCA checkout"""
        import shutil

        donor = tmp_path / "donor"
        donor.mkdir()
        make_mocca_repo(donor)
        repo = tmp_path / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", "git@example.org:mocca/mocca.git")
        shutil.copytree(donor / "src", repo / "src")
        with pytest.raises(moccarun.MoccaError, match="not tracked by git"):
            moccarun.validate_mocca_src(repo / "src")

    def test_makefile_without_mocca_target_rejected(self, project):
        (project.src / "makefile").write_text("all:\n\ttrue\n")
        git(project.src.parent, "add", "-A")
        git(project.src.parent, "commit", "-q", "-m", "mk")
        with pytest.raises(moccarun.MoccaError, match="no 'mocca' target"):
            moccarun.validate_mocca_src(project.src)

    def test_default_input_deleted_in_worktree(self, project):
        (project.src / "mocca.slurm").unlink()  # still tracked
        with pytest.raises(moccarun.MoccaError, match="not found"):
            moccarun.validate_mocca_src(project.src)

    def test_resolve_explicit_is_validated(self, project, tmp_path):
        with pytest.raises(moccarun.MoccaError):
            moccarun.resolve_mocca_src(tmp_path / "nowhere")

    def test_resolve_explicit_wins_over_discovery(self, project, tmp_path):
        assert moccarun.resolve_mocca_src(project.src, tmp_path) == project.src


class TestResolveBinary:
    def test_file(self, tmp_path):
        (tmp_path / "m").write_text("")
        assert moccarun.resolve_mocca_binary(tmp_path / "m") == tmp_path / "m"

    def test_directory(self, tmp_path):
        (tmp_path / "mocca").write_text("")
        assert moccarun.resolve_mocca_binary(tmp_path) == tmp_path / "mocca"

    def test_missing(self, tmp_path):
        with pytest.raises(moccarun.MoccaError):
            moccarun.resolve_mocca_binary(tmp_path / "nope")

import os
from unittest.mock import patch

import pytest

import moccarun
from moccarun import get_user_email


@pytest.fixture
def git_email(monkeypatch):
    """control what `git config user.email` returns"""

    def set_(value):
        monkeypatch.setattr(moccarun, "git_user_email", lambda: value)

    return set_


class TestGetUserEmail:
    """Tests for get_user_email(): CLI > MOCCARUN_EMAIL > git config > EMAIL"""

    def test_cli_email_returns_directly(self):
        assert get_user_email("test@example.com") == "test@example.com"

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "env@example.com"})
    def test_env_email_beats_git(self, git_email):
        git_email("git@example.com")
        assert get_user_email() == "env@example.com"

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "", "EMAIL": "system@example.com"})
    def test_git_config_email(self, git_email):
        git_email("git@example.com")
        assert get_user_email() == "git@example.com"

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "", "EMAIL": "system@example.com"})
    def test_email_env_last_fallback(self, git_email):
        git_email(None)
        assert get_user_email() == "system@example.com"

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "", "EMAIL": ""})
    def test_no_email_raises_error(self, git_email):
        git_email(None)
        with pytest.raises(ValueError, match="No email provided"):
            get_user_email()


class TestGitUserEmail:
    def test_reads_global_gitconfig(self, tmp_path, monkeypatch):
        (tmp_path / ".gitconfig").write_text("[user]\n\temail = git@example.com\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)  # not inside a repo with its own user.email
        assert moccarun.git_user_email() == "git@example.com"

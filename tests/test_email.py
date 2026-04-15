import os
import pytest
from unittest.mock import patch
from pathlib import Path
from configparser import ConfigParser
import tempfile


class TestGetUserEmail:
    """Tests for get_user_email() function."""

    def test_cli_email_returns_directly(self):
        """CLI argument should return immediately."""
        from moccarun import get_user_email

        assert get_user_email("test@example.com") == "test@example.com"

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "env@example.com"})
    def test_env_email_fallback(self):
        """MOCCARUN_EMAIL should be used when no CLI arg."""
        from moccarun import get_user_email

        assert get_user_email() == "env@example.com"

    @patch.dict(
        os.environ, {"MOCCARUN_EMAIL": "", "EMAIL": "system@example.com"}, clear=True
    )
    def test_email_env_fallback(self):
        """EMAIL should be used as last fallback."""
        from moccarun import get_user_email

        # Must also mock gitconfig to not interfere
        with patch.object(Path, "home", return_value=Path("/nonexistent")):
            assert get_user_email() == "system@example.com"

    def test_no_email_raises_error(self):
        """Should raise ValueError when no email available."""
        from moccarun import get_user_email

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, "home", return_value=Path("/nonexistent")):
                with pytest.raises(ValueError, match="No email provided"):
                    get_user_email()

    @patch.dict(os.environ, {"MOCCARUN_EMAIL": "", "EMAIL": ""}, clear=True)
    def test_gitconfig_fallback(self, tmp_path):
        """Should read from ~/.gitconfig if present."""
        # Create temp gitconfig
        gitconfig = tmp_path / ".gitconfig"
        parser = ConfigParser()
        parser.read(gitconfig)
        gitconfig.write_text("[user]\nemail = git@example.com\n")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            from moccarun import get_user_email

            # Clear MOCCARUN_EMAIL
            result = get_user_email()
            assert result == "git@example.com"

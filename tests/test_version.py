import re
import tomllib
from pathlib import Path


class TestVersionConsistency:
    """Tests for version consistency between pyproject.toml and code."""

    def test_version_matches_pyproject(self):
        """__VERSION__ should match version in pyproject.toml."""
        # Read pyproject.toml
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            toml_version = tomllib.load(f)["project"]["version"]

        # Read code version
        from moccarun import __VERSION__

        assert __VERSION__ == toml_version, (
            f"Version mismatch: __VERSION__={__VERSION__}, pyproject.toml={toml_version}"
        )

    def test_version_format(self):
        """Version should be a 10-digit YYMMDDHHMM timestamp."""
        from moccarun import __VERSION__

        assert re.fullmatch(r"\d{10}", __VERSION__), (
            f"Version '{__VERSION__}' should be a 10-digit YYMMDDHHMM timestamp"
        )

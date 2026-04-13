import sys
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
        """Version should follow semantic versioning."""
        from moccarun import __VERSION__

        parts = __VERSION__.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"

        # Major and minor should be numeric
        assert parts[0].isdigit(), f"Major version '{parts[0]}' should be numeric"
        assert parts[1].isdigit(), f"Minor version '{parts[1]}' should be numeric"

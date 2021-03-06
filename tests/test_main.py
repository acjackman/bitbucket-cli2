"""Test cases for the __main__ module."""
import pytest
from click.testing import CliRunner

from bitbucket_cli2 import __main__


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_help_menu(runner: CliRunner) -> None:
    """It exits with a status code of zero."""
    result = runner.invoke(__main__.cli, "--help")
    print(result.output)
    assert result.exit_code == 0

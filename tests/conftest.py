from devtools import pformat
import pytest

from filen import FilenConfig

filen_config_key = pytest.StashKey[FilenConfig]()


def pytest_configure(config: pytest.Config):
    config.stash[filen_config_key] = FilenConfig()


def pytest_report_header(config: pytest.Config):
    return pformat(config.stash[filen_config_key])


@pytest.fixture(scope='session')
def config(pytestconfig: pytest.Config) -> FilenConfig:
    return pytestconfig.stash[filen_config_key]

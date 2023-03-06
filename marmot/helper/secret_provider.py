"""Secret provider module
"""
import typing as t
from os import getenv
from enum import Enum
from getpass import getpass
from secrets import token_urlsafe
from .logging import LOGGER


def _env_secret_provider() -> t.Optional[bytes]:
    secret = getenv('MARMOT_PK_SECRET', None)
    if not secret:
        LOGGER.warning(
            "cannot find MARMOT_PK_SECRET environment variable, private key"
        )
        return None
    return secret.encode()


def _getpass_secret_provider() -> t.Optional[bytes]:
    secret = getpass("private key secret please: ")
    if not secret:
        return None
    return secret.encode()


def _genpass_secret_provider() -> t.Optional[bytes]:
    secret = token_urlsafe(16)
    print(f"genpass generated secret: {secret}")
    return secret.encode()


class SecretProviderBackend(Enum):
    """Secret provider backend"""

    ENV = 'env'
    GETPASS = 'getpass'
    GENPASS = 'genpass'


SECRET_PROVIDERS = [sp.value for sp in SecretProviderBackend]


_BACKEND = {
    SecretProviderBackend.ENV: _env_secret_provider,
    SecretProviderBackend.GETPASS: _getpass_secret_provider,
    SecretProviderBackend.GENPASS: _genpass_secret_provider,
}


class _SecretProvider:
    """Secret provider singleton"""

    def __init__(self):
        self._backend = _BACKEND[SecretProviderBackend.GETPASS]

    def select(self, backend: SecretProviderBackend):
        """Initialize provider backend"""
        self._backend = _BACKEND[backend]

    def fetch(self) -> t.Optional[bytes]:
        """Fetch secret"""
        return self._backend()


SECRET_PROVIDER = _SecretProvider()

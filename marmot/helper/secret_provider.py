"""Secret provider module
"""
import typing as t
from os import getenv
from enum import Enum
from getpass import getpass
from secrets import token_urlsafe


def _env_secret_provider(backend_argv: t.List[str]) -> t.Optional[bytes]:
    evn = 'MARMOT_PK_SECRET'
    if backend_argv:
        evn = backend_argv[0]
    secret = getenv(evn, None)
    if not secret:
        return None
    return secret.encode()


def _getpass_secret_provider(backend_argv: t.List[str]) -> t.Optional[bytes]:
    prompt = "passphrase please: "
    if backend_argv:
        prompt = backend_argv[0]
    secret = getpass(prompt)
    if not secret:
        return None
    return secret.encode()


def _genpass_secret_provider(_backend_argv: t.List[str]) -> t.Optional[bytes]:
    secret = token_urlsafe(16)
    print(f"genpass generated secret: {secret}")
    return secret.encode()


class SecretProviderBackend(Enum):
    """Secret provider backend"""

    ENV = 'env'
    GETPASS = 'getpass'
    GENPASS = 'genpass'


_BACKEND = {
    SecretProviderBackend.ENV: _env_secret_provider,
    SecretProviderBackend.GETPASS: _getpass_secret_provider,
}


class _SecretProvider:
    """Secret provider singleton"""

    def __init__(self):
        self._backend = _BACKEND[SecretProviderBackend.GETPASS]
        self._backend_argv = []

    def init(self, backend: SecretProviderBackend, backend_argv: t.List[str]):
        """Initialize provider backend"""
        self._backend = _BACKEND[backend]
        self._backend_argv = backend_argv

    def fetch(self) -> t.Optional[bytes]:
        """Fetch secret"""
        return self._backend(self._backend_argv)


SECRET_PROVIDER = _SecretProvider()

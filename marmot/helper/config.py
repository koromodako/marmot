"""Marmot configuration helper
"""
import typing as t
from re import compile as re_compile
from json import JSONDecodeError, loads, dumps
from pathlib import Path
from dataclasses import dataclass, field
from yarl import URL
from .crypto import (
    MarmotPublicKey,
    MarmotPrivateKey,
    load_marmot_public_key,
    dump_marmot_public_key,
    load_marmot_private_key,
    dump_marmot_private_key,
)
from .logging import LOGGER


CLIENT_PATTERN = re_compile(r'[a-z\d]+([_\-][a-z\d]+)*')
CHANNEL_PATTERN = CLIENT_PATTERN

DEFAULT_REDIS_URL = 'redis://localhost'
DEFAULT_REDIS_MAXCONN = 50
DEFAULT_REDIS_TRIMFREQ = 300
DEFAULT_MARMOT_HOST = '127.0.0.1'
DEFAULT_MARMOT_PORT = 1758
DEFAULT_MARMOT_URL = URL.build(
    scheme='http', host=DEFAULT_MARMOT_HOST, port=DEFAULT_MARMOT_PORT
)
DEFAULT_MARMOT_CAPATH = Path.home() / '.config' / 'marmot' / 'ca.pem'


class MarmotConfigError(Exception):
    """Raised when configuration error is encountered"""


@dataclass
class MarmotChannelConfig:
    """Marmot channel configuration"""

    whistlers: t.Set[str] = field(default_factory=set)
    listeners: t.Set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, dct) -> 'MarmotChannelConfig':
        """Create configuration object from dict"""
        return cls(
            whistlers=set(dct.get('whistlers', [])),
            listeners=set(dct.get('listeners', [])),
        )

    def to_dict(self):
        """Convert configuration object to JSON serializable dict"""
        return {
            'whistlers': list(sorted(list(self.whistlers))),
            'listeners': list(sorted(list(self.listeners))),
        }

    def add_whistler(self, guid):
        """Add whistler"""
        self.whistlers.add(guid)

    def rem_whistler(self, guid):
        """Delete whistler"""
        self.whistlers.discard(guid)

    def add_listener(self, guid):
        """Add listener"""
        self.listeners.add(guid)

    def rem_listener(self, guid):
        """Delete listener"""
        self.listeners.discard(guid)


@dataclass
class MarmotRedisConfig:
    """Marmot redis configuration"""

    url: str = DEFAULT_REDIS_URL
    trim_freq: int = DEFAULT_REDIS_TRIMFREQ
    max_connections: int = DEFAULT_REDIS_MAXCONN

    @classmethod
    def from_dict(cls, dct) -> 'MarmotRedisConfig':
        """Create configuration object from dict"""
        return cls(
            url=dct.get('url', DEFAULT_REDIS_URL),
            trim_freq=int(dct.get('trim_freq', DEFAULT_REDIS_TRIMFREQ)),
            max_connections=int(
                dct.get('max_connections', DEFAULT_REDIS_MAXCONN)
            ),
        )

    def to_dict(self):
        """Convert configuration object to JSON serializable dict"""
        return {
            'url': self.url,
            'trim_freq': self.trim_freq,
            'max_connections': self.max_connections,
        }


def validate_guid(guid: str) -> str:
    """Validate client against naming convention"""
    if not CLIENT_PATTERN.fullmatch(guid):
        raise MarmotConfigError("guid naming error!")
    return guid


def validate_channel(channel: str) -> str:
    """Validate channel against naming convention"""
    if not CHANNEL_PATTERN.fullmatch(channel):
        raise MarmotConfigError("channel naming error!")
    return channel


@dataclass
class MarmotServerConfig:
    """Marmot server configuration"""

    host: str
    port: int
    redis: MarmotRedisConfig
    clients: t.Mapping[str, MarmotPublicKey]
    channels: t.Mapping[str, MarmotChannelConfig]

    @classmethod
    def from_dict(cls, dct) -> t.Optional['MarmotServerConfig']:
        """Create configuration object from dict"""
        if dct is None:
            return None
        return cls(
            host=dct.get('host', DEFAULT_MARMOT_HOST),
            port=int(dct.get('port', DEFAULT_MARMOT_PORT)),
            redis=MarmotRedisConfig.from_dict(dct.get('redis', {})),
            clients={
                validate_guid(guid): load_marmot_public_key(pubkey)
                for guid, pubkey in dct.get('clients', {}).items()
            },
            channels={
                validate_channel(name): MarmotChannelConfig.from_dict(conf)
                for name, conf in dct.get('channels', {}).items()
            },
        )

    def to_dict(self):
        """Convert configuration object to JSON serializable dict"""
        return {
            "host": self.host,
            "port": self.port,
            "redis": self.redis.to_dict(),
            "clients": {
                client: dump_marmot_public_key(pubkey)
                for client, pubkey in self.clients.items()
            },
            "channels": {
                name: channel.to_dict()
                for name, channel in self.channels.items()
            },
        }

    def add_client(self, guid, pubkey):
        """Add client"""
        validate_guid(guid)
        if guid in self.clients:
            LOGGER.warning("client already exist, client creation canceled.")
            return
        pubkey = load_marmot_public_key(pubkey)
        self.clients[guid] = pubkey

    def rem_client(self, guid):
        """Delete client"""
        if guid not in self.clients:
            LOGGER.warning("client does not exist, client removal canceled.")
            return
        # remove client from channels
        for channel in self.channels.values():
            channel.rem_whistler(guid)
            channel.rem_listener(guid)
        # remove client
        self.clients.pop(guid, None)

    def add_channel(self, channel):
        """Add channel"""
        validate_channel(channel)
        if channel in self.channels:
            LOGGER.warning("channel already exist, channel creation canceled.")
            return
        self.channels[channel] = MarmotChannelConfig()

    def rem_channel(self, channel):
        """Delete channel"""
        if channel not in self.channels:
            LOGGER.warning("client does not exist, client removal canceled.")
            return
        self.channels.pop(channel, None)

    def add_whistler(self, channel, guid):
        """Add whistler"""
        if guid not in self.clients:
            LOGGER.warning(
                "cannot add unknown client to whistlers, registration canceled."
            )
            return
        channel = self.channels.get(channel)
        if not channel:
            return
        channel.add_whistler(guid)

    def rem_whistler(self, channel, guid):
        """Delete whistler"""
        channel = self.channels.get(channel)
        if not channel:
            return
        channel.rem_whistler(guid)

    def add_listener(self, channel, guid):
        """Add listener"""
        if guid not in self.clients:
            LOGGER.warning(
                "cannot add unknown client to whistlers, registration canceled."
            )
            return
        channel = self.channels.get(channel)
        if not channel:
            return
        channel.add_listener(guid)

    def rem_listener(self, channel, guid):
        """Delete listener"""
        channel = self.channels.get(channel)
        if not channel:
            return
        channel.rem_listener(guid)


@dataclass
class MarmotClientConfig:
    """Marmot client configuration"""

    guid: str
    url: URL
    capath: Path
    prikey: MarmotPrivateKey

    @classmethod
    def from_dict(cls, dct) -> t.Optional['MarmotClientConfig']:
        """Create configuration object from dict"""
        if dct is None:
            return None
        return cls(
            guid=validate_guid(dct['guid']),
            url=URL(dct.get('url', str(DEFAULT_MARMOT_URL))),
            capath=Path(dct.get('capath', str(DEFAULT_MARMOT_CAPATH))),
            prikey=load_marmot_private_key(dct['prikey']),
        )

    def to_dict(self):
        """Convert configuration object to JSON serializable dict"""
        return {
            "guid": self.guid,
            "url": str(self.url),
            "capath": str(self.capath),
            "prikey": dump_marmot_private_key(self.prikey),
        }


@dataclass
class MarmotConfig:
    """Marmot configuration"""

    server: t.Optional[MarmotServerConfig] = None
    client: t.Optional[MarmotClientConfig] = None

    @classmethod
    def from_filepath(cls, filepath: Path) -> 'MarmotConfig':
        """Load marmot configuration from filepath"""
        if not filepath.is_file():
            raise MarmotConfigError(
                f"cannot find configuration file: {filepath}"
            )
        try:
            dct = loads(filepath.read_text())
        except PermissionError as exc:
            raise MarmotConfigError(
                f"cannot read configuration file: {filepath}"
            ) from exc
        except JSONDecodeError as exc:
            raise MarmotConfigError(
                f"cannot decode configuration file: {filepath}"
            ) from exc
        try:
            return cls(
                server=MarmotServerConfig.from_dict(dct.get('server')),
                client=MarmotClientConfig.from_dict(dct.get('client')),
            )
        except ValueError as exc:
            raise MarmotConfigError("wrong passphrase!") from exc
        except KeyError as exc:
            raise MarmotConfigError(
                f"cannot decode configuration file: {filepath}"
            ) from exc
        except Exception as exc:
            raise MarmotConfigError(f"{exc}") from exc

    def to_filepath(self, filepath: Path):
        """Dump marmot configuration to filepath"""
        dct = {}
        if self.client:
            dct['client'] = self.client.to_dict()
        if self.server:
            dct['server'] = self.server.to_dict()
        filepath.write_text(dumps(dct, indent=2))

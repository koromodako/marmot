"""Marmot main module
"""
import typing as t
from enum import Enum
from json import loads
from asyncio import Event
from dataclasses import dataclass
from aiohttp import (
    TCPConnector,
    ClientTimeout,
    ClientSession,
    ServerTimeoutError,
    ClientConnectorError,
)
from rich.prompt import Confirm
from .helper.api import MarmotAPIMessage, MarmotMessageLevel
from .helper.crypto import (
    sign_marmot_data_digest,
    create_marmot_ssl_context,
    hash_marmot_listen_params,
)
from .helper.config import MarmotConfig
from .helper.logging import LOGGER
from .helper.event_source import event_source_stream


class MarmotRole(Enum):
    """Marmot role"""

    LISTENER = 'listener'
    WHISTLER = 'whistler'


@dataclass
class MarmotMessage:
    """Marmot message"""

    channel: str
    content: str
    level: MarmotMessageLevel = MarmotMessageLevel.INFO
    whistler: str = ''


class Marmot:
    """Marmot"""

    def __init__(self, config: MarmotConfig, client: ClientSession):
        self._config = config
        self._client = client

    @staticmethod
    def create_client(role: MarmotRole, config: MarmotConfig):
        """Create HTTP client session"""
        LOGGER.info("connecting to %s", config.client.url)
        is_secure = config.client.url.scheme == 'https'
        if not is_secure:
            LOGGER.critical("/!\\ USING INSECURE PROTOCOL /!\\")
            if not Confirm.ask("do you accept the risk?"):
                raise KeyboardInterrupt
        sslctx = (
            create_marmot_ssl_context(config.client.capath)
            if is_secure
            else None
        )
        timeout = (
            ClientTimeout(sock_connect=5)
            if role == MarmotRole.LISTENER
            else ClientTimeout(total=60, sock_connect=5)
        )
        connector = TCPConnector(ssl=sslctx)
        return ClientSession(
            connector=connector,
            base_url=config.client.url,
            timeout=timeout,
            raise_for_status=False,
        )

    async def _listen(
        self, channels: t.List[str], stop_event: Event
    ) -> t.Iterator[MarmotMessage]:
        guid = self._config.client.guid
        headers = {
            'X-Marmot-GUID': guid,
            'X-Marmot-Channels': '|'.join(channels),
            'X-Marmot-Signature': sign_marmot_data_digest(
                self._config.client.prikey,
                hash_marmot_listen_params(guid, channels),
            ),
        }
        async with self._client.get('/api/listen', headers=headers) as resp:
            if resp.status != 200:
                LOGGER.error("server sent status code: %s", resp.status)
                return
            async for evt in event_source_stream(resp, stop_event):
                event = evt.event.decode()
                if event == 'reset':
                    LOGGER.warning("server sent a reset notification.")
                    break
                if event == 'whistle':
                    dct = loads(evt.data.decode())
                    message = MarmotAPIMessage.from_dict(dct)
                    yield MarmotMessage(
                        channel=message.channel,
                        content=message.content,
                        level=message.level,
                        whistler=message.whistler,
                    )

    async def listen(
        self, channels: t.Set[str], stop_event: Event
    ) -> t.Iterator[MarmotMessage]:
        """Listen to one or more channels"""
        channels = list(sorted(list(channels)))
        try:
            async for message in self._listen(channels, stop_event):
                yield message
        except ServerTimeoutError:
            LOGGER.critical("server seems unreachable!")
        except ClientConnectorError:
            LOGGER.critical("server refused connection!")

    async def _whistle(self, messages: t.List[MarmotMessage]) -> t.List[bool]:
        payload = {
            'messages': [
                MarmotAPIMessage(
                    channel=message.channel,
                    content=message.content,
                    whistler=self._config.client.guid,
                    level=message.level,
                )
                .sign(
                    self._config.client.prikey,
                )
                .to_dict()
                for message in messages
            ]
        }
        async with self._client.post('/api/whistle', json=payload) as resp:
            body = await resp.json()
            return body['published']

    async def whistle(self, messages: t.List[MarmotMessage]) -> t.List[bool]:
        """Whistle messages"""
        try:
            return await self._whistle(messages)
        except ServerTimeoutError:
            LOGGER.critical("server seems unreachable!")
        except ClientConnectorError:
            LOGGER.critical("server refused connection!")
        return []

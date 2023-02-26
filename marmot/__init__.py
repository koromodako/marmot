"""Marmot main module
"""
import typing as t
from json import loads
from dataclasses import dataclass
from .server import MarmotAPIMessage, MarmotMessageLevel
from .helper.crypto import hash_marmot_data, sign_marmot_data_digest
from .helper.logging import LOGGER
from .helper.event_source import event_source_stream


@dataclass
class MarmotMessage:
    """Marmot message"""

    channel: str
    content: str
    level: MarmotMessageLevel = MarmotMessageLevel.INFO


class Marmot:
    """Marmot whistler"""

    def __init__(self, config, http_client):
        self._config = config
        self._http_client = http_client

    async def listen(self, channel, message_processing_cb):
        """Listen in a channel"""
        url = f'/listen/{channel}'
        guid = self._config.client.guid
        headers = {
            'X-Marmot-GUID': guid,
            'X-Marmot-Signature': sign_marmot_data_digest(
                self._config.client.prikey,
                hash_marmot_data(':'.join([guid, channel]).encode()),
            )
        }
        async with self._http_client.get(url, headers=headers) as resp:
            if resp.status != 200:
                LOGGER.error("server sent status code: %s", resp.status)
                return
            async for evt in event_source_stream(resp):
                event = evt.event.decode()
                if event == 'reset':
                    LOGGER.warning("server sent a reset notification.")
                    break
                if event == 'whistle':
                    message_processing_cb(loads(evt.data.decode()))

    async def whistle(self, messages: t.List[MarmotMessage]):
        """Whistle messages"""
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
        async with self._http_client.post('/whistle', json=payload) as resp:
            body = await resp.json()
            return body['published'], body['unauthorized']

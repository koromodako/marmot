"""Marmot notification module
"""
import typing as t
from redis.asyncio import Redis
from .api import MarmotAPIMessage
from .config import (
    MarmotConfig,
    MarmotRedisConfig,
    MarmotServerConfig,
    MarmotChannelConfig,
)
from .crypto import (
    MarmotPublicKey,
    hash_marmot_data,
    load_marmot_public_key,
    dump_marmot_public_key,
    verify_marmot_data_digest,
)
from .logging import LOGGER


KEY_MARMOT_CLIENTS = 'marmot::clients'
KEY_MARMOT_CHANNELS = 'marmot::channels'


def _marmot_channel_stream(channel):
    return f'marmot::{channel}::stream'


def _marmot_channel_listeners(channel):
    return f'marmot::{channel}::listeners'


def _marmot_channel_whistlers(channel):
    return f'marmot::{channel}::whistlers'


class MarmotServerBackend:
    """Marmot server backend"""

    def __init__(self, url: str, max_connections: int):
        self._url = url
        self._max_connections = max_connections
        self._redis = Redis.from_url(
            url,
            encoding='utf-8',
            max_connections=min(max_connections, 10),
            decode_responses=True,
        )

    async def close(self):
        """Close underlying redis connections"""
        await self._redis.close()

    async def add_client(self, guid: str, pubkey: MarmotPublicKey):
        """Add or update a client"""
        await self._redis.hset(
            KEY_MARMOT_CLIENTS, guid, dump_marmot_public_key(pubkey)
        )

    async def del_client(self, guid: str):
        """Delete a client"""
        await self._redis.hdel(KEY_MARMOT_CLIENTS, guid)
        async for key in self._redis.scan_iter(_marmot_channel_listeners('*')):
            await self._redis.hdel(key, guid)
        async for key in self._redis.scan_iter(_marmot_channel_whistlers('*')):
            await self._redis.srem(key, guid)

    async def add_channel(self, name: str, channel: MarmotChannelConfig):
        """Add or update a channel"""
        # intialize channel's stream
        key = _marmot_channel_stream(name)
        count = await self._redis.exists(key)
        if count == 0:
            last_message_id = await self._redis.xadd(
                key, MarmotAPIMessage().to_dict()
            )
        else:
            info = await self._redis.xinfo_stream(key)
            last_message_id = info['last-generated-id']
        key = _marmot_channel_whistlers(name)
        for whistler in channel.whistlers:
            await self._redis.sadd(key, whistler)
        key = _marmot_channel_listeners(name)
        for listener in channel.listeners:
            count = await self._redis.hexists(key, listener)
            if count == 1:
                continue
            await self._redis.hset(key, listener, last_message_id)
        await self._redis.sadd(KEY_MARMOT_CHANNELS, name)

    async def del_channel(self, name: str):
        """Delete a channel"""
        await self._redis.srem(KEY_MARMOT_CHANNELS, name)
        await self._redis.delete(_marmot_channel_stream(name))
        await self._redis.delete(_marmot_channel_listeners(name))
        await self._redis.delete(_marmot_channel_whistlers(name))

    async def add_listener(self, channel: str, listener: str):
        """Add listener to channel"""
        key = _marmot_channel_listeners(channel)
        count = await self._redis.hexists(key, listener)
        if count == 1:
            return
        stream_key = _marmot_channel_stream(channel)
        info = await self._redis.xinfo_stream(stream_key)
        last_message_id = info['last-generated-id']
        await self._redis.hset(key, listener, last_message_id)

    async def del_listener(self, channel: str, listener: str):
        """Delete listener from channel"""
        await self._redis.hdel(_marmot_channel_listeners(channel), listener)

    async def add_whistler(self, channel: str, whistler: str):
        """Add whistler to channel"""
        await self._redis.sadd(_marmot_channel_whistlers(channel), whistler)

    async def del_whistler(self, channel: str, whistler: str):
        """Delete whistler from channel"""
        await self._redis.srem(_marmot_channel_whistlers(channel), whistler)

    async def push(self, message: MarmotAPIMessage):
        """Push a message in the stream"""
        key = _marmot_channel_stream(message.channel)
        await self._redis.xadd(key, message.to_dict())

    async def pull(
        self, channel: str, listener: str
    ) -> t.Iterator[t.Tuple[str, MarmotAPIMessage]]:
        """Pull pending messages"""
        key = _marmot_channel_listeners(channel)
        last_message_id = await self._redis.hget(key, listener)
        key = _marmot_channel_stream(channel)
        streams = await self._redis.xread({key: last_message_id})
        for _, messages in streams:
            for message_id, message in messages:
                yield message_id, MarmotAPIMessage.from_dict(message)

    async def ack(self, channel: str, listener: str, message_id: str):
        """Ack that previously pulled message was processed successfully"""
        key = _marmot_channel_listeners(channel)
        await self._redis.hset(key, listener, message_id)

    async def trim(self, channel: str):
        """Remove delivered messages from stream"""
        print(f"trim called: {channel}")
        key = _marmot_channel_listeners(channel)
        listeners = await self._redis.hgetall(key)
        print(listeners)
        key = _marmot_channel_stream(channel)
        minid = None
        mincount = None
        for last_message_id in listeners.values():
            count = len(await self._redis.xrange(key, max=last_message_id))
            if not mincount or count < mincount:
                minid = last_message_id
                mincount = count
        print(minid)
        print(mincount)
        if minid:
            print("calling xtrim with minid")
            await self._redis.xtrim(key, minid=minid)
        else:
            print("calling xtrim with maxlen")
            await self._redis.xtrim(key, maxlen=1)
        return mincount

    async def trim_all(self):
        """Call trim for each channel"""
        channels = await self._redis.smembers(KEY_MARMOT_CHANNELS)
        for channel in channels:
            await self.trim(channel)

    async def load(self, config: MarmotConfig):
        """Load marmot configuration as backend state"""
        clients = set(await self._redis.hkeys(KEY_MARMOT_CLIENTS))
        channels = set(await self._redis.smembers(KEY_MARMOT_CHANNELS))
        clients_to_del = clients.difference(set(config.server.clients.keys()))
        channels_to_del = channels.difference(
            set(config.server.channels.keys())
        )
        for channel_to_del in channels_to_del:
            await self.del_channel(channel_to_del)
        for client_to_del in clients_to_del:
            await self.del_client(client_to_del)
        for guid, pubkey in config.server.clients.items():
            await self.add_client(guid, pubkey)
        for name, channel in config.server.channels.items():
            await self.add_channel(name, channel)

    async def dump(self) -> MarmotConfig:
        """Dump backend state as marmot configuration"""
        clients = set(await self._redis.hgetall(KEY_MARMOT_CLIENTS))
        channels = []
        channels_ = set(await self._redis.smembers(KEY_MARMOT_CHANNELS))
        for channel in channels_:
            listeners = await self._redis.hkeys(
                _marmot_channel_listeners(channel)
            )
            whistlers = await self._redis.smembers(
                _marmot_channel_whistlers(channel)
            )
            channels.append(
                MarmotChannelConfig(listeners=listeners, whistlers=whistlers)
            )
        return MarmotConfig(
            server=MarmotServerConfig(
                host='',
                port=0,
                redis=MarmotRedisConfig(
                    url=self._url,
                    max_connections=self._max_connections,
                ),
                clients=clients,
                channels=channels,
            )
        )

    async def can_listen(self, guid: str, channel: str, signature: str):
        """Determine if marmot can listen"""
        pubkey = await self._redis.hget(KEY_MARMOT_CLIENTS, guid)
        if not pubkey:
            LOGGER.error("unknown client: %s", guid)
            return False
        count = await self._redis.sismember(KEY_MARMOT_CHANNELS, channel)
        if count == 0:
            LOGGER.error("unknown channel: %s", channel)
            return False
        key = _marmot_channel_listeners(channel)
        count = await self._redis.hexists(key, guid)
        if count == 0:
            LOGGER.error("unknown channel listener: %s", guid)
            return False
        digest = hash_marmot_data(':'.join([guid, channel]).encode())
        pubkey = load_marmot_public_key(pubkey)
        if not verify_marmot_data_digest(pubkey, digest, signature):
            LOGGER.error("signature verification failed.")
            return False
        return True

    async def can_whistle(self, message):
        """Determine if marmot can whistle"""
        guid = message.whistler
        channel = message.channel
        pubkey = await self._redis.hget(KEY_MARMOT_CLIENTS, guid)
        if not pubkey:
            LOGGER.error("unknown client: %s", guid)
            return False
        count = await self._redis.sismember(KEY_MARMOT_CHANNELS, channel)
        if count == 0:
            LOGGER.error("unknown channel: %s", channel)
            return False
        key = _marmot_channel_whistlers(channel)
        count = await self._redis.sismember(key, guid)
        if count == 0:
            LOGGER.error("unknown channel whistler: %s", guid)
            return False
        pubkey = load_marmot_public_key(pubkey)
        if not message.verify(pubkey):
            LOGGER.error("signature verification failed.")
            return False
        return True

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
    load_marmot_public_key,
    dump_marmot_public_key,
    hash_marmot_listen_params,
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
            max_connections=min(max(max_connections, 10), 2 ** 15),
            decode_responses=True,
        )

    async def close(self):
        """Close underlying redis connections"""
        await self._redis.close()
        # building Redis instance using from_url implies that we need to close
        # the underlying connection_pool explicitly
        await self._redis.connection_pool.disconnect()

    async def add_client(self, guid: str, pubkey: MarmotPublicKey):
        """Add or update a client"""
        await self._redis.hset(
            KEY_MARMOT_CLIENTS, guid, dump_marmot_public_key(pubkey)
        )

    async def rem_client(self, guid: str):
        """Delete a client"""
        # remove client from the list
        await self._redis.hdel(KEY_MARMOT_CLIENTS, guid)
        # iterate channels to remove client from listeners
        async for key in self._redis.scan_iter(_marmot_channel_listeners('*')):
            await self._redis.hdel(key, guid)
        # iterate channels to remove client from whistlers
        async for key in self._redis.scan_iter(_marmot_channel_whistlers('*')):
            await self._redis.srem(key, guid)

    async def add_channel(self, name: str, channel: MarmotChannelConfig):
        """Add or update a channel"""
        # ensure channel stream exists
        key = _marmot_channel_stream(name)
        count = await self._redis.exists(key)
        if count == 0:
            await self._redis.xadd(key, MarmotAPIMessage().to_dict())
        # remove whistlers if necessary
        key = _marmot_channel_whistlers(name)
        whistlers = set(await self._redis.smembers(key))
        for whistler in whistlers.difference(channel.whistlers):
            await self.rem_whistler(name, whistler)
        # add whistlers if necessary
        for whistler in channel.whistlers:
            await self.add_whistler(name, whistler)
        key = _marmot_channel_listeners(name)
        # remove listeners if necessary
        listeners = set(await self._redis.hkeys(key))
        for listener in listeners.difference(channel.listeners):
            await self.rem_listener(name, listener)
        # add listeners if necessary
        for listener in channel.listeners:
            await self.add_listener(name, listener)
        # ensure channel is registered
        await self._redis.sadd(KEY_MARMOT_CHANNELS, name)

    async def rem_channel(self, name: str):
        """Delete a channel"""
        # unregister channel
        await self._redis.srem(KEY_MARMOT_CHANNELS, name)
        # delete channel stream
        await self._redis.delete(_marmot_channel_stream(name))
        # delete channel's listeners structure
        await self._redis.delete(_marmot_channel_listeners(name))
        # delete channel's whistlers structure
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

    async def rem_listener(self, channel: str, listener: str):
        """Delete listener from channel"""
        await self._redis.hdel(_marmot_channel_listeners(channel), listener)

    async def add_whistler(self, channel: str, whistler: str):
        """Add whistler to channel"""
        await self._redis.sadd(_marmot_channel_whistlers(channel), whistler)

    async def rem_whistler(self, channel: str, whistler: str):
        """Delete whistler from channel"""
        await self._redis.srem(_marmot_channel_whistlers(channel), whistler)

    async def push(self, message: MarmotAPIMessage):
        """Push a message in the stream"""
        key = _marmot_channel_stream(message.channel)
        await self._redis.xadd(key, message.to_dict())

    async def pull(
        self, channels: t.List[str], listener: str
    ) -> t.Iterator[
        t.Union[t.Tuple[str, MarmotAPIMessage], t.Tuple[None, None]]
    ]:
        """Pull pending messages"""
        states = {}
        for channel in channels:
            key = _marmot_channel_listeners(channel)
            last_message_id = await self._redis.hget(key, listener)
            if not last_message_id:
                continue
            key = _marmot_channel_stream(channel)
            states[key] = last_message_id
        # listener cannot read theses channels anymore
        if not states:
            yield None, None
            return
        streams = await self._redis.xread(states)
        for _, messages in streams:
            for message_id, message in messages:
                yield message_id, MarmotAPIMessage.from_dict(message)

    async def ack(self, channel: str, listener: str, message_id: str):
        """Ack that previously pulled message was processed successfully"""
        key = _marmot_channel_listeners(channel)
        await self._redis.hset(key, listener, message_id)

    async def trim(self, channel: str):
        """Remove delivered messages from stream"""
        key = _marmot_channel_listeners(channel)
        listeners = await self._redis.hgetall(key)
        key = _marmot_channel_stream(channel)
        minid = None
        mincount = None
        for last_message_id in listeners.values():
            count = len(await self._redis.xrange(key, max=last_message_id))
            if not mincount or count < mincount:
                minid = last_message_id
                mincount = count
        if minid:
            # if listeners trim up to the oldest unread message
            LOGGER.info("trim messages: (%s, %s)", channel, mincount)
            await self._redis.xtrim(key, minid=minid)
        else:
            # if no listener at all trim all messages
            LOGGER.info("trim messages: (%s, all)", channel)
            await self._redis.xtrim(key, maxlen=1)
        return mincount

    async def trim_all(self):
        """Call trim for each channel"""
        channels = await self._redis.smembers(KEY_MARMOT_CHANNELS)
        for channel in channels:
            await self.trim(channel)

    async def load(self, fs_config: MarmotConfig):
        """Load marmot configuration as backend state"""
        # retrieve backened configuration
        be_clients = set(await self._redis.hkeys(KEY_MARMOT_CLIENTS))
        be_channels = set(await self._redis.smembers(KEY_MARMOT_CHANNELS))
        # compute changes
        clients_to_rem = be_clients.difference(
            set(fs_config.server.clients.keys())
        )
        channels_to_rem = be_channels.difference(
            set(fs_config.server.channels.keys())
        )
        # apply changes
        for channel_to_rem in channels_to_rem:
            await self.rem_channel(channel_to_rem)
        for client_to_rem in clients_to_rem:
            await self.rem_client(client_to_rem)
        for guid, pubkey in fs_config.server.clients.items():
            await self.add_client(guid, pubkey)
        for name, channel in fs_config.server.channels.items():
            await self.add_channel(name, channel)

    async def dump(self) -> MarmotConfig:
        """Dump backend state as marmot configuration"""
        clients = await self._redis.hgetall(KEY_MARMOT_CLIENTS)
        clients = {
            guid: load_marmot_public_key(pubkey)
            for guid, pubkey in clients.items()
        }
        channels = {}
        channels_ = set(await self._redis.smembers(KEY_MARMOT_CHANNELS))
        for channel in channels_:
            listeners = await self._redis.hkeys(
                _marmot_channel_listeners(channel)
            )
            whistlers = await self._redis.smembers(
                _marmot_channel_whistlers(channel)
            )
            channels[channel] = MarmotChannelConfig(
                listeners=set(listeners), whistlers=set(whistlers)
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

    async def can_listen(
        self, guid: str, channels: t.Set[str], signature: str
    ):
        """Determine if marmot can listen"""
        pubkey = await self._redis.hget(KEY_MARMOT_CLIENTS, guid)
        if not pubkey:
            LOGGER.error("unknown client: %s", guid)
            return False
        for channel in channels:
            count = await self._redis.sismember(KEY_MARMOT_CHANNELS, channel)
            if count == 0:
                LOGGER.error("unknown channel: %s", channel)
                return False
            key = _marmot_channel_listeners(channel)
            count = await self._redis.hexists(key, guid)
            if count == 0:
                LOGGER.error("unknown channel listener: %s", guid)
                return False
        digest = hash_marmot_listen_params(guid, channels)
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

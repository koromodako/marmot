"""Marmot server
"""
from enum import Enum
from uuid import uuid4
from json import dumps
from asyncio import Semaphore, Event, sleep
from pathlib import Path
from argparse import ArgumentParser
from dataclasses import dataclass
from aiohttp import web
from aioredis import Redis
from aiohttp_sse import sse_response
from .__version__ import version
from .helper.crypto import (
    MarmotPublicKey,
    MarmotPrivateKey,
    hash_marmot_data,
    sign_marmot_data_digest,
    verify_marmot_data_digest,
)
from .helper.config import MarmotConfig
from .helper.logging import LOGGER
from .helper.authorization import can_listen, can_whistle


BANNER = f"Marmot Server {version}"


class MarmotMessageLevel(Enum):
    """Marmot message level"""

    CRITICAL = 'critical'
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'
    DEBUG = 'debug'


@dataclass
class MarmotAPIMessage:
    """Marmot API message"""

    channel: str
    content: str
    whistler: str
    signature: str = None
    guid: str = str(uuid4())
    level: MarmotMessageLevel = MarmotMessageLevel.INFO

    @property
    def digest(self):
        """Message digest"""
        message_data = ':'.join([self.channel, self.level.value, self.content])
        return hash_marmot_data(message_data.encode())

    @classmethod
    def from_dict(cls, dct):
        """Create message object from dict"""
        return cls(
            channel=dct['channel'],
            content=dct['content'],
            whistler=dct['whistler'],
            guid=dct['guid'],
            level=MarmotMessageLevel(dct['level']),
            signature=dct['signature'],
        )

    def to_dict(self):
        """Convert message object to JSON serializable dict"""
        return {
            'channel': self.channel,
            'content': self.content,
            'whistler': self.whistler,
            'guid': self.guid,
            'level': self.level.value,
            'signature': self.signature,
        }

    def sign(self, prikey: MarmotPrivateKey):
        """Update message signature"""
        self.signature = sign_marmot_data_digest(prikey, self.digest)
        return self

    def verify(self, pubkey: MarmotPublicKey):
        """Verify message signature"""
        return verify_marmot_data_digest(pubkey, self.digest, self.signature)


async def _messages_from_request(request):
    body = await request.json()
    if 'messages' not in body:
        raise web.HTTPBadRequest
    for message in body['messages']:
        yield MarmotAPIMessage.from_dict(message)


async def _forward_messages_from(request, pubsub, stop_event):
    async with sse_response(request, sep='\r\n') as resp:
        # set ping interval
        resp.ping_interval = 5
        while True:
            # internal ping task ends prematurely meaning that the client
            # closed the connection, exit
            # not nice, pending https://github.com/aio-libs/aiohttp-sse/issues/391
            if resp._ping_task.done():
                break
            # server is shutting down, notify the client and exit
            if stop_event.is_set():
                await resp.send('reset', event='reset')
                break
            # retrieve next message from channel and forward it
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message is not None:
                await resp.send(dumps(message['data']), event='whistle')
            # sleep before processing next message
            await sleep(1)


async def _listen(request):
    try:
        guid = request.headers['X-Marmot-GUID']
        signature = request.headers['X-Marmot-Signature']
    except KeyError as exc:
        raise web.HTTPBadRequest from exc
    channel = request.match_info.get('channel')
    config = request.app['config']
    if not can_listen(config, guid, channel, signature):
        LOGGER.warning(
            "prevented unauthorized listen attempt from %s@%s on #%s",
            guid,
            request.remote,
            channel,
        )
        raise web.HTTPForbidden
    listen_sem = request.app['listen_sem']
    stop_event = request.app['stop_event']
    if listen_sem.locked():
        raise web.HTTPConflict
    async with listen_sem:
        LOGGER.info(
            "client [%s](%s) is listening on #%s",
            guid,
            request.remote,
            channel,
        )
        redis = request.app['redis']
        pubsub = redis.pubsub()
        async with pubsub as psc:
            await psc.subscribe(channel)
            try:
                await _forward_messages_from(request, psc, stop_event)
            except ConnectionResetError:
                LOGGER.info(
                    "connection reset caught for [%s](%s) (listening on #%s)",
                    guid,
                    request.remote,
                    channel,
                )
            finally:
                await psc.unsubscribe(channel)
        await pubsub.close()


async def _whistle(request):
    redis = request.app['redis']
    config = request.app['config']
    published = []
    unauthorized = []
    async for message in _messages_from_request(request):
        if not can_whistle(config, message):
            LOGGER.warning(
                "prevented unauthorized whistle attempt from %s@%s on #%s",
                message.whistler,
                request.remote,
                message.channel,
            )
            unauthorized.append(message.uid)
            continue
        LOGGER.info(
            "client [%s](%s) is whistling on #%s",
            message.whistler,
            request.remote,
            message.channel,
        )
        await redis.publish(
            message.channel,
            dumps(
                {
                    'whistler': message.whistler,
                    'level': message.level.value,
                    'content': message.content,
                }
            ),
        )
        published.append(message.guid)
    return web.json_response(
        {'published': published, 'unauthorized': unauthorized}
    )


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config', '-c', type=Path, default=Path('marmot.json'), help="TODO"
    )
    parser.add_argument('--host', help="TODO")
    parser.add_argument('--port', type=int, help="TODO")
    parser.add_argument('--redis-url', help="TODO")
    parser.add_argument('--redis-max-connections', help="TODO")
    return parser.parse_args()


async def _on_startup(webapp):
    LOGGER.info("starting up...")
    webapp['stop_event'].clear()


async def _on_shutdown(webapp):
    print()
    LOGGER.info("shutting down...")
    webapp['stop_event'].set()
    await sleep(1)


async def _on_cleanup(webapp):
    LOGGER.info("cleaning up...")
    await webapp['redis'].close()
    await sleep(1)


def app():
    """Application entrypoint"""
    LOGGER.info(BANNER)
    args = _parse_args()
    try:
        config = MarmotConfig.from_filepath(args.config)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")
        return
    if not config.server:
        LOGGER.critical("cannot find server configuration in: %s", args.config)
        return
    host = args.host or config.server.host
    port = args.port or config.server.port
    redis_url = args.redis_url or config.server.redis.url
    redis_max_connections = min(
        (args.redis_max_connections or config.server.redis.max_connections),
        10,
    )
    webapp = web.Application()
    webapp['redis'] = Redis.from_url(
        redis_url,
        max_connections=redis_max_connections,
        encoding='utf-8',
        decode_responses=True,
    )
    webapp['config'] = config
    webapp['listen_sem'] = Semaphore(redis_max_connections - 1)
    webapp['stop_event'] = Event()

    webapp.add_routes(
        [
            method(pattern, handler)
            for pattern, method, handler in [
                ('/api/listen/{channel}', web.get, _listen),
                ('/api/whistle', web.post, _whistle),
            ]
        ]
    )
    webapp.on_startup.append(_on_startup)
    webapp.on_shutdown.append(_on_shutdown)
    webapp.on_cleanup.append(_on_cleanup)
    web.run_app(webapp, host=host, port=port)

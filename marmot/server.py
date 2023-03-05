"""Marmot server
"""
import typing as t
from json import dumps
from asyncio import CancelledError, Event, sleep, create_task
from pathlib import Path
from argparse import ArgumentParser
from aiohttp import web
from aiohttp_sse import sse_response
from .__version__ import version
from .helper.api import MarmotAPIMessage
from .helper.config import MarmotConfig
from .helper.logging import LOGGER
from .helper.backend import MarmotServerBackend


BANNER = f"Marmot Server {version}"


async def _forward_messages_from(request, guid: str, channels: t.List[str]):
    backend = request.app['backend']
    stop_event = request.app['stop_event']
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
            async for message_id, message in backend.pull(channels, guid):
                await resp.send(dumps(message.to_dict()), event='whistle')
                await backend.ack(message.channel, guid, message_id)
            # sleep before processing next message
            await sleep(1)


async def _listen(request):
    # NOTE: a semaphore might be needed here to limit the number of
    #       simultaneous listeners
    try:
        guid = request.headers['X-Marmot-GUID']
        channels = set(request.headers['X-Marmot-Channels'].split('|'))
        signature = request.headers['X-Marmot-Signature']
    except KeyError as exc:
        raise web.HTTPBadRequest from exc
    backend = request.app['backend']
    can_listen = await backend.can_listen(guid, channels, signature)
    channels = list(sorted(channels))
    if not can_listen:
        LOGGER.warning(
            "client unauthorized listen attempt: (%s, %s, %s)",
            guid,
            request.remote,
            '|'.join(channels),
        )
        raise web.HTTPForbidden
    LOGGER.info(
        "client is listening: (%s, %s, %s)",
        guid,
        request.remote,
        '|'.join(channels),
    )
    try:
        await _forward_messages_from(request, guid, channels)
    except ConnectionResetError:
        LOGGER.info(
            "client connection reset caught: (%s, %s, %s)",
            guid,
            request.remote,
            '|'.join(channels),
        )


async def _whistle(request):
    backend = request.app['backend']
    body = await request.json()
    if 'messages' not in body:
        raise web.HTTPBadRequest
    try:
        messages = [
            MarmotAPIMessage.from_dict(message) for message in body['messages']
        ]
    except (ValueError, KeyError) as exc:
        raise web.HTTPBadRequest from exc
    published = []
    for message in messages:
        can_whistle = await backend.can_whistle(message)
        if not can_whistle:
            LOGGER.warning(
                "client unauthorized whistle attempt: (%s, %s, %s)",
                message.whistler,
                request.remote,
                message.channel,
            )
            published.append(False)
            continue
        LOGGER.info(
            "client is whistling: (%s, %s, %s)",
            message.whistler,
            request.remote,
            message.channel,
        )
        await backend.push(message)
        published.append(True)
    return web.json_response({'published': published})


async def _backend_trim_task(backend):
    """Trim backend channels every 20 seconds"""
    while True:
        await backend.trim_all()
        await sleep(20)


async def _on_startup(webapp):
    LOGGER.info("starting up...")
    webapp['stop_event'].clear()
    LOGGER.info("loading configuration...")
    await webapp['backend'].load(webapp['config'])
    LOGGER.info("starting background tasks...")
    webapp['background_tasks'] = []
    for name, task in (
        ('backend_trim_task', _backend_trim_task(webapp['backend'])),
    ):
        LOGGER.info("starting task: %s", name)
        webapp['background_tasks'].append(create_task(task, name=name))


async def _on_shutdown(webapp):
    print()
    LOGGER.info("shutting down...")
    webapp['stop_event'].set()
    LOGGER.info("terminating background tasks...")
    for task in webapp['background_tasks']:
        task.cancel()
        LOGGER.info("waiting for canceled task: %s", task.get_name())
        try:
            await task
        except CancelledError:
            LOGGER.info("task successfully canceled.")
    await sleep(1)


async def _on_cleanup(webapp):
    LOGGER.info("cleaning up...")
    await webapp['backend'].close()
    await sleep(1)


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="marmot configuration file",
    )
    parser.add_argument('--host', help="marmot server host")
    parser.add_argument('--port', type=int, help="marmot server port")
    parser.add_argument(
        '--redis-url',
        help="marmot redis url, do not add credentials in this url",
    )
    parser.add_argument(
        '--redis-max-connections',
        type=int,
        help="marmot redis max connections",
    )
    return parser.parse_args()


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
    webapp = web.Application()
    webapp['config'] = config
    webapp['backend'] = MarmotServerBackend(
        args.redis_url or config.server.redis.url,
        args.redis_max_connections or config.server.redis.max_connections,
    )
    webapp['stop_event'] = Event()
    webapp.add_routes(
        [
            method(pattern, handler)
            for pattern, method, handler in [
                ('/api/listen', web.get, _listen),
                ('/api/whistle', web.post, _whistle),
            ]
        ]
    )
    webapp.on_startup.append(_on_startup)
    webapp.on_shutdown.append(_on_shutdown)
    webapp.on_cleanup.append(_on_cleanup)
    web.run_app(webapp, host=host, port=port)

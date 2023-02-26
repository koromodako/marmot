"""Marmot client
"""
from pathlib import Path
from asyncio import new_event_loop
from argparse import ArgumentParser
from aiohttp import ClientSession, ClientTimeout
from . import Marmot
from .__version__ import version
from .helper.config import MarmotConfig, MarmotConfigError
from .helper.logging import LOGGER


BANNER = f"Marmot Listen {version}"


def _process_message_cb(message):
    """"""
    print(message)


async def _async_listen(args):
    """"""
    config = MarmotConfig.from_filepath(args.config)
    async with ClientSession(
        base_url=config.client.url, timeout=ClientTimeout()
    ) as http_client:
        marmot = Marmot(config, http_client)
        await marmot.listen(args.channel, _process_message_cb)


def _listen(args):
    """"""
    loop = new_event_loop()
    loop.run_until_complete(_async_listen(args))
    loop.close()


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config', '-c', type=Path, default=Path('marmot.json'), help="TODO"
    )
    parser.add_argument('--host', help="TODO")
    parser.add_argument('--port', type=int, help="TODO")
    parser.add_argument('channel', help="TODO")
    parser.set_defaults(func=_listen)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    LOGGER.info(BANNER)
    args = _parse_args()
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

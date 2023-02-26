"""Marmot client
"""
from pathlib import Path
from asyncio import new_event_loop
from argparse import ArgumentParser
from aiohttp import ClientSession
from . import Marmot, MarmotMessage
from .server import MarmotMessageLevel
from .__version__ import version
from .helper.config import MarmotConfig, MarmotConfigError
from .helper.logging import LOGGER


BANNER = f"Marmot Whistle {version}"


def _whistle(args):
    """"""

    async def _async_whistle(args):
        """"""
        config = MarmotConfig.from_filepath(args.config)
        async with ClientSession(base_url=config.client.url) as http_client:
            marmot = Marmot(config, http_client)
            published, unauthorized = await marmot.whistle(
                [
                    MarmotMessage(
                        channel=args.channel,
                        content=args.message,
                        level=args.level,
                    )
                ]
            )
            print(f"published: {published}")
            print(f"unauthorized: {unauthorized}")

    # _whistle implementation
    loop = new_event_loop()
    loop.run_until_complete(_async_whistle(args))
    loop.close()


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config', '-c', type=Path, default=Path('marmot.json'), help="TODO"
    )
    parser.add_argument('--host', help="TODO")
    parser.add_argument('--port', type=int, help="TODO")
    parser.add_argument(
        '--level',
        '-l',
        type=MarmotMessageLevel,
        default=MarmotMessageLevel.INFO,
        help="TODO",
    )
    parser.add_argument('channel', help="TODO")
    parser.add_argument('message', help="TODO")
    parser.set_defaults(func=_whistle)
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

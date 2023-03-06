"""Marmot client
"""
from os import getenv
from pathlib import Path
from asyncio import new_event_loop
from argparse import ArgumentParser
from . import Marmot, MarmotRole, MarmotMessage
from .__version__ import version
from .helper.api import MARMOT_MESSAGE_LEVELS, MarmotMessageLevel
from .helper.config import MarmotConfig, MarmotConfigError
from .helper.logging import LOGGER
from .helper.secret_provider import (
    SECRET_PROVIDER,
    SECRET_PROVIDERS,
    SecretProviderBackend,
)


BANNER = f"Marmot Whistle {version}"


async def _async_whistle(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.client:
        LOGGER.error("cannot find client configuration in: %s", args.config)
        return
    async with Marmot.create_client(MarmotRole.WHISTLER, config) as client:
        marmot = Marmot(config, client)
        published = await marmot.whistle(
            [
                MarmotMessage(
                    channel=args.channel,
                    content=args.content,
                    level=args.level,
                )
            ]
        )
        print(f"published: {published}")


def _whistle(args):
    loop = new_event_loop()
    loop.run_until_complete(_async_whistle(args))
    loop.close()


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="marmot configuration file",
    )
    parser.add_argument(
        '--secret-provider',
        '--sp',
        type=SecretProviderBackend,
        default=SecretProviderBackend.GETPASS,
        help=f"marmot secret provider, one of {{{SECRET_PROVIDERS}}}",
    )
    parser.add_argument('--host', help="marmot server host")
    parser.add_argument('--port', type=int, help="marmot server port")
    parser.add_argument(
        '--level',
        '-l',
        type=MarmotMessageLevel,
        default=MarmotMessageLevel(getenv('MARMOT_MSG_LEVEL', 'INFO')),
        help=f"marmot message level, one of {{{MARMOT_MESSAGE_LEVELS}}}",
    )
    parser.add_argument(
        '--channel',
        default=getenv('MARMOT_MSG_CHANNEL', 'CHANNEL_PLACEHOLDER'),
        help="marmot channel",
    )
    parser.add_argument(
        '--content',
        default=getenv('MARMOT_MSG_CONTENT', 'CONTENT_PLACEHOLDER'),
        help="marmot message content",
    )
    parser.set_defaults(func=_whistle)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    LOGGER.info(BANNER)
    args = _parse_args()
    SECRET_PROVIDER.select(args.secret_provider)
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

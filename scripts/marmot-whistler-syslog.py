#!/urs/bin/env python3
"""Marmot whistler processing syslog messages invoked using
syslog-ng program() function
"""
from sys import stdin
from pathlib import Path
from asyncio import new_event_loop
from argparse import ArgumentParser
from marmot import Marmot, MarmotRole, MarmotMessage
from marmot.helper.api import MarmotMessageLevel
from marmot.helper.config import MarmotConfig, MarmotConfigError
from marmot.helper.logging import LOGGER
from marmot.helper.secret_provider import (
    SECRET_PROVIDER, SecretProviderBackend
)


def _message_from_line(line) -> MarmotMessage:
    # ----- BEGIN CUSTOM LINE PROCESSING -----
    channel = 'default'
    content = line
    level = MarmotMessageLevel.DEBUG
    # ----- END   CUSTOM LINE PROCESSING -----
    return MarmotMessage(
        channel=channel,
        content=content,
        level=level,
    )


async def _async_whistle(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.client:
        LOGGER.error("cannot find client configuration in: %s", args.config)
        return
    async with Marmot.create_client(MarmotRole.WHISTLER, config) as client:
        marmot = Marmot(config, client)
        published = await marmot.whistle(
            [_message_from_line(line.rstrip()) for line in stdin]
        )
        print(published)


def _whistle(args):
    loop = new_event_loop()
    loop.run_until_complete(_async_whistle(args))
    loop.close()


def _parse_args():
    parser = ArgumentParser(description="Marmot Whistler for Syslog")
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="marmot configuration file",
    )
    parser.set_defaults(func=_whistle)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    args = _parse_args()
    SECRET_PROVIDER.select(SecretProviderBackend.ENV)
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

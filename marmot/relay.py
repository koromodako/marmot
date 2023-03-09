"""Marmot client
"""
from signal import SIGINT, SIGTERM
from pathlib import Path
from asyncio import Event, new_event_loop
from argparse import ArgumentParser
from yarl import URL
from rich.console import Console
from . import Marmot, MarmotRole
from .__version__ import version
from .helper.config import MarmotConfig, MarmotClientConfig, MarmotConfigError
from .helper.logging import LOGGER
from .helper.secret_provider import (
    SECRET_PROVIDER,
    SECRET_PROVIDERS,
    SecretProviderBackend,
)


BANNER = f"Marmot Relay {version}"
CONSOLE = Console()
STOP_EVENT = Event()


async def _async_relay(args):
    l_config = MarmotConfig.from_filepath(args.config)
    if not l_config.client:
        LOGGER.error("cannot find client configuration in: %s", args.config)
        return
    w_config = MarmotConfig(
        client=MarmotClientConfig(
            guid=l_config.client.guid,
            url=args.url,
            capath=args.capath,
            prikey=l_config.client.prikey,
        )
    )
    async with Marmot.create_client(MarmotRole.LISTENER, l_config) as l_client:
        async with Marmot.create_client(
            MarmotRole.WHISTLER, w_config
        ) as w_client:
            l_marmot = Marmot(l_config, l_client)
            w_marmot = Marmot(w_config, w_client)
            async for message in l_marmot.listen(
                set(args.channels), STOP_EVENT
            ):
                published = await w_marmot.whistle([message])
                if published[0]:
                    LOGGER.info(
                        "relayed message from %s in %s",
                        message.whistler,
                        message.channel,
                    )
                else:
                    LOGGER.error(
                        "failed to relay message from %s in %s",
                        message.whistler,
                        message.channel,
                    )


def _termination_handler():
    print()
    LOGGER.info("terminating, please wait...")
    STOP_EVENT.set()


def _relay(args):
    STOP_EVENT.clear()
    loop = new_event_loop()
    loop.add_signal_handler(SIGINT, _termination_handler)
    loop.add_signal_handler(SIGTERM, _termination_handler)
    loop.run_until_complete(_async_relay(args))
    loop.close()


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="marmot client configuration file",
    )
    parser.add_argument(
        '--secret-provider',
        '--sp',
        type=SecretProviderBackend,
        default=SecretProviderBackend.GETPASS,
        help=f"marmot secret provider, one of {{{','.join(SECRET_PROVIDERS)}}}",
    )
    parser.add_argument(
        'channels',
        metavar='channel',
        nargs='+',
        help="marmot channel to listen to",
    )
    parser.add_argument('url', type=URL, help="Destination URL")
    parser.add_argument('capath', type=Path, help="Destination CA path")
    parser.set_defaults(func=_relay)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    LOGGER.info(BANNER, extra={'highlighter': None})
    args = _parse_args()
    SECRET_PROVIDER.select(args.secret_provider)
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot relay configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

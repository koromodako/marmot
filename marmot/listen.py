"""Marmot client
"""
from json import dumps
from signal import SIGINT, SIGTERM
from pathlib import Path
from asyncio import Event, new_event_loop, create_subprocess_exec
from argparse import ArgumentParser
from rich.markup import escape
from rich.console import Console
from . import Marmot, MarmotRole, MarmotMessage
from .__version__ import version
from .helper.api import MarmotMessageLevel
from .helper.config import MarmotConfig, MarmotConfigError
from .helper.logging import LOGGER
from .helper.secret_provider import (
    SECRET_PROVIDER,
    SECRET_PROVIDERS,
    SecretProviderBackend,
)


BANNER = f"Marmot Listen {version}"
CONSOLE = Console()
STOP_EVENT = Event()
LEVEL_STYLE_MAP = {
    MarmotMessageLevel.CRITICAL: 'blink bold reverse red',
    MarmotMessageLevel.ERROR: 'blink bold red',
    MarmotMessageLevel.WARNING: 'blink bold yellow',
    MarmotMessageLevel.INFO: 'blue',
    MarmotMessageLevel.DEBUG: 'green',
}


def _display(message: MarmotMessage):
    level = f"[{LEVEL_STYLE_MAP[message.level]}]{message.level.name:>8s}[/]"
    sender = f"[bold]{escape(message.channel)}[/]|{escape(message.whistler)}"
    line = f"[{level}]({sender}): {escape(message.content)}"
    CONSOLE.print(line)


async def _exec(executable: Path, message: MarmotMessage):
    process = await create_subprocess_exec(
        executable,
        env={
            'MARMOT_MSG_LEVEL': message.level.name,
            'MARMOT_MSG_CHANNEL': message.channel,
            'MARMOT_MSG_WHISTLER': message.whistler,
            'MARMOT_MSG_CONTENT': message.content,
        },
    )
    await process.wait()


async def _async_listen(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.client:
        LOGGER.error("cannot find client configuration in: %s", args.config)
        return
    async with Marmot.create_client(MarmotRole.LISTENER, config) as client:
        marmot = Marmot(config, client)
        async for message in marmot.listen(set(args.channels), STOP_EVENT):
            if args.json:
                print(dumps(message.to_dict()))
            else:
                _display(message)
            if args.executable:
                await _exec(args.executable, message)


def _termination_handler():
    print()
    LOGGER.info("terminating, please wait...")
    STOP_EVENT.set()


def _listen(args):
    STOP_EVENT.clear()
    loop = new_event_loop()
    loop.add_signal_handler(SIGINT, _termination_handler)
    loop.add_signal_handler(SIGTERM, _termination_handler)
    loop.run_until_complete(_async_listen(args))
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
    parser.add_argument('--json', action='store_true', help="JSON output")
    parser.add_argument('--host', help="marmot server host")
    parser.add_argument('--port', type=int, help="marmot server port")
    parser.add_argument(
        '--executable',
        '-e',
        type=Path,
        help="invoke executable with message properties passed in environment variables",
    )
    parser.add_argument(
        'channels',
        metavar='channel',
        nargs='+',
        help="marmot channel to listen to",
    )
    parser.set_defaults(func=_listen)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    LOGGER.info(BANNER, extra={'highlighter': None})
    args = _parse_args()
    SECRET_PROVIDER.select(args.secret_provider)
    if args.executable and not args.executable.is_file():
        args.executable = None
        LOGGER.warning(
            "cannot find file, --executable ignored: %s", args.executable
        )
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

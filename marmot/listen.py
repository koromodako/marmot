"""Marmot client

MIT License

Copyright (c) 2023 koromodako

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
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


async def _exec(script: Path, message: MarmotMessage):
    process = await create_subprocess_exec(
        script,
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
            _display(message)
            if args.script:
                await _exec(args.script, message)


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
    parser.add_argument('--host', help="marmot server host")
    parser.add_argument('--port', type=int, help="marmot server port")
    parser.add_argument(
        '--exec',
        type=Path,
        help="invoke executable with message properties passed in environment variables"
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
    LOGGER.info(BANNER)
    args = _parse_args()
    if args.script and not args.script.is_file():
        args.script = None
        LOGGER.warning("cannot find file, --script ignored: %s", args.script)
    try:
        args.func(args)
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")

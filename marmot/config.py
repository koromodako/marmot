"""Marmot config application
"""
from uuid import uuid4
from pathlib import Path
from argparse import ArgumentParser
from rich.box import ROUNDED
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.console import Console
from .__version__ import version
from .helper.config import (
    MarmotConfig,
    MarmotConfigError,
    MarmotRedisConfig,
    MarmotClientConfig,
    MarmotServerConfig,
    DEFAULT_REDIS_URL,
    DEFAULT_REDIS_MAXCONN,
    DEFAULT_MARMOT_HOST,
    DEFAULT_MARMOT_PORT,
    DEFAULT_MARMOT_URL,
)
from .helper.crypto import generate_marmot_private_key, dump_marmot_public_key
from .helper.logging import LOGGER


BANNER = f"Marmot Config {version}"
CONSOLE = Console()


def _init_client(args):
    config = MarmotConfig()
    if args.config.is_file():
        config = MarmotConfig.from_filepath(args.config)
    if config.client:
        LOGGER.warning(
            "client already initialized, client initialization canceled."
        )
        return
    config.client = MarmotClientConfig(
        guid=str(uuid4()),
        url=Prompt.ask(
            "please enter marmot server url", default=str(DEFAULT_MARMOT_URL)
        ),
        prikey=generate_marmot_private_key(),
    )
    config.to_filepath(args.config)


def _init_server(args):
    config = MarmotConfig()
    if args.config.is_file():
        config = MarmotConfig.from_filepath(args.config)
    if config.server:
        LOGGER.warning(
            "server already initialized, server initialization canceled."
        )
        return
    config.server = MarmotServerConfig(
        host=Prompt.ask(
            "please enter marmot host", default=DEFAULT_MARMOT_HOST
        ),
        port=int(
            Prompt.ask(
                "please enter marmot port", default=str(DEFAULT_MARMOT_PORT)
            )
        ),
        redis=MarmotRedisConfig(
            url=Prompt.ask(
                "please enter redis url", default=DEFAULT_REDIS_URL
            ),
            max_connections=int(
                Prompt.ask(
                    "please enter redis max connections",
                    default=str(DEFAULT_REDIS_MAXCONN),
                )
            ),
        ),
        clients={},
        channels={},
    )
    config.to_filepath(args.config)


def _show_client(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.client:
        LOGGER.error("cannot find client configuration in: %s", args.config)
        return
    pubkey = config.client.prikey.public_key()
    table = Table(title="Marmot Client Config", box=ROUNDED, expand=True)
    table.add_column("Property")
    table.add_column("Value")
    table.add_row("guid", config.client.guid)
    table.add_row("url", str(config.client.url))
    table.add_row("pubkey", dump_marmot_public_key(pubkey))
    CONSOLE.print(table)


def _show_server(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.server:
        LOGGER.error("cannot find server configuration in: %s", args.config)
        return
    table = Table(title="Marmot Server Config", box=ROUNDED, expand=True)
    table.add_column("Property")
    table.add_column("Value")
    table.add_row("host", config.server.host)
    table.add_row("port", str(config.server.port))
    table.add_row("redis.url", config.server.redis.url)
    table.add_row(
        "redis.max_connections", str(config.server.redis.max_connections)
    )
    CONSOLE.print(table)
    table = Table(
        title="Marmot Server Declared Clients", box=ROUNDED, expand=True
    )
    table.add_column("GUID")
    table.add_column("Public Key")
    for guid, pubkey in config.server.clients.items():
        table.add_row(guid, dump_marmot_public_key(pubkey))
    CONSOLE.print(table)
    root_node = Tree("server")
    for channel, conf in config.server.channels.items():
        channel_node = root_node.add(channel)
        listeners_node = channel_node.add("listeners")
        for listener in conf.listeners:
            listeners_node.add(listener)
        whistlers_node = channel_node.add("whistlers")
        for whistler in conf.whistlers:
            whistlers_node.add(whistler)
    CONSOLE.print(
        Panel(root_node, title="Marmot Server Declared Channels", box=ROUNDED)
    )


def _add_client(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_client(args.guid, args.pubkey)
    config.to_filepath(args.config)
    LOGGER.info("client added: %s", args.guid)


def _del_client(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_client(args.guid)
    config.to_filepath(args.config)
    LOGGER.info("client deleted: %s", args.guid)


def _add_channel(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_channel(args.channel)
    config.to_filepath(args.config)
    LOGGER.info("channel added: %s", args.channel)


def _del_channel(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_channel(args.channel)
    config.to_filepath(args.config)
    LOGGER.info("channel deleted: %s", args.channel)


def _add_whistler(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_whistler(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("#%s whistler added: %s", args.channel, args.guid)


def _del_whistler(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_whistler(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("#%s whistler deleted: %s", args.channel, args.guid)


def _add_listener(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_listener(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("#%s listener added: %s", args.channel, args.guid)


def _del_listener(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_listener(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("#%s listener deleted: %s", args.channel, args.guid)


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config', '-c', type=Path, default=Path('marmot.json'), help="TODO"
    )
    cmd = parser.add_subparsers(dest='cmd')
    cmd.required = True
    init_client = cmd.add_parser('init-client', help="TODO")
    init_client.set_defaults(func=_init_client)
    init_server = cmd.add_parser('init-server', help="TODO")
    init_server.set_defaults(func=_init_server)
    show_client = cmd.add_parser('show-client', help="TODO")
    show_client.set_defaults(func=_show_client)
    show_server = cmd.add_parser('show-server', help="TODO")
    show_server.set_defaults(func=_show_server)
    add_client = cmd.add_parser('add-client', help="TODO")
    add_client.add_argument('guid', help="TODO")
    add_client.add_argument('pubkey', help="TODO")
    add_client.set_defaults(func=_add_client)
    del_client = cmd.add_parser('del-client', help="TODO")
    del_client.add_argument('guid', help="TODO")
    del_client.set_defaults(func=_del_client)
    add_channel = cmd.add_parser('add-channel', help="TODO")
    add_channel.add_argument('channel', help="TODO")
    add_channel.set_defaults(func=_add_channel)
    del_channel = cmd.add_parser('del-channel', help="TODO")
    del_channel.add_argument('channel', help="TODO")
    del_channel.set_defaults(func=_del_channel)
    add_whistler = cmd.add_parser('add-whistler', help="TODO")
    add_whistler.add_argument('channel', help="TODO")
    add_whistler.add_argument('guid', help="TODO")
    add_whistler.set_defaults(func=_add_whistler)
    del_whistler = cmd.add_parser('del-whistler', help="TODO")
    del_whistler.add_argument('channel', help="TODO")
    del_whistler.add_argument('guid', help="TODO")
    del_whistler.set_defaults(func=_del_whistler)
    add_listener = cmd.add_parser('add-listener', help="TODO")
    add_listener.add_argument('channel', help="TODO")
    add_listener.add_argument('guid', help="TODO")
    add_listener.set_defaults(func=_add_listener)
    del_listener = cmd.add_parser('del-listener', help="TODO")
    del_listener.add_argument('channel', help="TODO")
    del_listener.add_argument('guid', help="TODO")
    del_listener.set_defaults(func=_del_listener)
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

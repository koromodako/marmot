"""Marmot config application
"""
from uuid import uuid4
from asyncio import new_event_loop, sleep
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
    DEFAULT_MARMOT_CAPATH,
)
from .helper.crypto import generate_marmot_private_key, dump_marmot_public_key
from .helper.backend import MarmotServerBackend
from .helper.logging import LOGGER
from .helper.secret_provider import SECRET_PROVIDER, SecretProviderBackend


BANNER = f"Marmot Config {version}"
CONSOLE = Console()


async def _init_client(args):
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
        url=(
            str(DEFAULT_MARMOT_URL)
            if args.use_defaults
            else Prompt.ask(
                "please enter marmot server url",
                default=str(DEFAULT_MARMOT_URL),
            )
        ),
        capath=(
            str(DEFAULT_MARMOT_CAPATH)
            if args.use_defaults
            else Path(
                Prompt.ask(
                    "please enter marmot server CA path",
                    default=str(DEFAULT_MARMOT_CAPATH),
                )
            )
        ),
        prikey=generate_marmot_private_key(),
    )
    if args.use_defaults:
        SECRET_PROVIDER.init(SecretProviderBackend.GENPASS, [])
    config.to_filepath(args.config)


async def _init_server(args):
    config = MarmotConfig()
    if args.config.is_file():
        config = MarmotConfig.from_filepath(args.config)
    if config.server:
        LOGGER.warning(
            "server already initialized, server initialization canceled."
        )
        return
    config.server = MarmotServerConfig(
        host=(
            DEFAULT_MARMOT_HOST
            if args.use_defaults
            else Prompt.ask(
                "please enter marmot host", default=DEFAULT_MARMOT_HOST
            )
        ),
        port=int(
            str(DEFAULT_MARMOT_PORT)
            if args.use_defaults
            else Prompt.ask(
                "please enter marmot port", default=str(DEFAULT_MARMOT_PORT)
            )
        ),
        redis=MarmotRedisConfig(
            url=(
                DEFAULT_REDIS_URL
                if args.use_defaults
                else Prompt.ask(
                    "please enter redis url", default=DEFAULT_REDIS_URL
                )
            ),
            max_connections=int(
                str(DEFAULT_REDIS_MAXCONN)
                if args.use_defaults
                else Prompt.ask(
                    "please enter redis max connections",
                    default=str(DEFAULT_REDIS_MAXCONN),
                )
            ),
        ),
        clients={},
        channels={},
    )
    config.to_filepath(args.config)


async def _show_client(args):
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


async def _show_server(args):
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
    for name, channel in config.server.channels.items():
        channel_node = root_node.add(name)
        listeners_node = channel_node.add("listeners")
        for listener in channel.listeners:
            listeners_node.add(listener)
        whistlers_node = channel_node.add("whistlers")
        for whistler in channel.whistlers:
            whistlers_node.add(whistler)
    CONSOLE.print(
        Panel(root_node, title="Marmot Server Declared Channels", box=ROUNDED)
    )


async def _add_client(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_client(args.guid, args.pubkey)
    config.to_filepath(args.config)
    LOGGER.info("client added: %s", args.guid)


async def _del_client(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_client(args.guid)
    config.to_filepath(args.config)
    LOGGER.info("client deleted: %s", args.guid)


async def _add_channel(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_channel(args.channel)
    config.to_filepath(args.config)
    LOGGER.info("channel added: %s", args.channel)


async def _del_channel(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_channel(args.channel)
    config.to_filepath(args.config)
    LOGGER.info("channel deleted: %s", args.channel)


async def _add_whistler(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_whistler(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("whistler added: (%s, %s)", args.channel, args.guid)


async def _del_whistler(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_whistler(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("whistler deleted: (%s, %s)", args.channel, args.guid)


async def _add_listener(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.add_listener(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("listener added: (%s, %s)", args.channel, args.guid)


async def _del_listener(args):
    config = MarmotConfig.from_filepath(args.config)
    config.server.del_listener(args.channel, args.guid)
    config.to_filepath(args.config)
    LOGGER.info("listener deleted: (%s, %s)", args.channel, args.guid)


async def _diff(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.server:
        LOGGER.error("cannot find server configuration in: %s", args.config)
        return
    backend = MarmotServerBackend(
        args.redis_url or config.server.redis.url,
        args.redis_max_connections or config.server.redis.max_connections,
    )
    try:
        backend_config = await backend.dump()
    finally:
        await backend.close()
    raise NotImplementedError


async def _load(args):
    config = MarmotConfig.from_filepath(args.config)
    if not config.server:
        LOGGER.error("cannot find server configuration in: %s", args.config)
        return
    backend = MarmotServerBackend(
        args.redis_url or config.server.redis.url,
        args.redis_max_connections or config.server.redis.max_connections,
    )
    LOGGER.info("loading config in backend...")
    try:
        await backend.load(config)
    finally:
        await backend.close()
        await sleep(1)
    LOGGER.info("loading done")


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="Marmot configuration file",
    )
    cmd = parser.add_subparsers(dest='cmd')
    cmd.required = True
    init_client = cmd.add_parser(
        'init-client', help="Initialize client configuration"
    )
    init_client.add_argument(
        '--use-defaults',
        action='store_true',
        help="Use default values, non-interactive mode",
    )
    init_client.set_defaults(async_func=_init_client)
    init_server = cmd.add_parser(
        'init-server', help="Initialize server configuration"
    )
    init_server.add_argument(
        '--use-defaults',
        action='store_true',
        help="Use default values, non-interactive mode",
    )
    init_server.set_defaults(async_func=_init_server)
    show_client = cmd.add_parser(
        'show-client', help="Show client configuration"
    )
    show_client.set_defaults(async_func=_show_client)
    show_server = cmd.add_parser(
        'show-server', help="Show server configuration"
    )
    show_server.set_defaults(async_func=_show_server)
    add_client = cmd.add_parser('add-client', help="Add a client")
    add_client.add_argument('guid', help="GUID of the client to add")
    add_client.add_argument('pubkey', help="Public key of the client to add")
    add_client.set_defaults(async_func=_add_client)
    del_client = cmd.add_parser('del-client', help="Delete a client")
    del_client.add_argument('guid', help="GUID of the client to delete")
    del_client.set_defaults(async_func=_del_client)
    add_channel = cmd.add_parser('add-channel', help="Add a channel")
    add_channel.add_argument('channel', help="Channel to add")
    add_channel.set_defaults(async_func=_add_channel)
    del_channel = cmd.add_parser('del-channel', help="Delete a channel")
    del_channel.add_argument('channel', help="Channel to delete")
    del_channel.set_defaults(async_func=_del_channel)
    add_whistler = cmd.add_parser(
        'add-whistler', help="Add a whistler to a channel"
    )
    add_whistler.add_argument('channel', help="Channel to update")
    add_whistler.add_argument('guid', help="GUID of the whistler to add")
    add_whistler.set_defaults(async_func=_add_whistler)
    del_whistler = cmd.add_parser(
        'del-whistler', help="Delete a whistler from a channel"
    )
    del_whistler.add_argument('channel', help="Channel to update")
    del_whistler.add_argument('guid', help="GUID of the whistler to delete")
    del_whistler.set_defaults(async_func=_del_whistler)
    add_listener = cmd.add_parser(
        'add-listener', help="Add a listener to a channel"
    )
    add_listener.add_argument('channel', help="Channel to update")
    add_listener.add_argument('guid', help="GUID of the listener to add")
    add_listener.set_defaults(async_func=_add_listener)
    del_listener = cmd.add_parser(
        'del-listener', help="Delete a listener from a channel"
    )
    del_listener.add_argument('channel', help="Channel to update")
    del_listener.add_argument('guid', help="GUID of the listener to delete")
    del_listener.set_defaults(async_func=_del_listener)
    diff = cmd.add_parser(
        'diff', help="Show differences between backend and config"
    )
    diff.add_argument(
        '--redis-url',
        help="Marmot redis url, do not add credentials in this url",
    )
    diff.add_argument(
        '--redis-max-connections',
        type=int,
        help="Marmot redis max connections",
    )
    diff.set_defaults(async_func=_diff)
    load = cmd.add_parser('load', help="Load config in backend")
    load.add_argument(
        '--redis-url',
        help="Marmot redis url, do not add credentials in this url",
    )
    load.add_argument(
        '--redis-max-connections',
        type=int,
        help="Marmot redis max connections",
    )
    load.set_defaults(async_func=_load)
    return parser.parse_args()


def app():
    """Aplication entrypoint"""
    LOGGER.info(BANNER)
    args = _parse_args()
    loop = new_event_loop()
    try:
        loop.run_until_complete(args.async_func(args))
    except MarmotConfigError as exc:
        LOGGER.error("marmot configuration error: %s", exc)
    except KeyboardInterrupt:
        print()
        LOGGER.warning("operation canceled.")
    finally:
        loop.close()

"""Marmot config application
"""
from re import compile as re_compile
from uuid import uuid4
from asyncio import new_event_loop
from pathlib import Path
from argparse import ArgumentParser
from rich.box import ROUNDED
from rich.text import Text
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.console import Console
from .__version__ import version
from .helper.config import (
    validate_guid,
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
ADDED_STYLE = 'green'
DELETED_STYLE = 'red'

UNIX_URL_PATTERN = re_compile(r'password=([^&\n]+)')
REDIS_URL_PATTERN = re_compile(r'(rediss?)://([^:/]+):([^@/]+)@(.*)')


def _redact_redis_url(url: str) -> str:
    for pattern, repl in (
        (UNIX_URL_PATTERN, 'password=[REDACTED]'),
        (REDIS_URL_PATTERN, '\1://\2:[REDACTED]@\4'),
    ):
        url = pattern.sub(repl, url)
    return url


def _load_client_config(config: Path):
    fs_config = MarmotConfig.from_filepath(config)
    if not fs_config.client:
        LOGGER.error("cannot find client configuration in: %s", config)
        raise MarmotConfigError("cannot find client configuration")
    return fs_config


def _load_server_config(config: Path):
    fs_config = MarmotConfig.from_filepath(config)
    if not fs_config.server:
        LOGGER.error("cannot find server configuration in: %s", config)
        raise MarmotConfigError("cannot find server configuration")
    return fs_config


async def _init_client(args):
    fs_config = MarmotConfig()
    if args.config.is_file():
        fs_config = MarmotConfig.from_filepath(args.config)
    if fs_config.client:
        LOGGER.warning(
            "client already initialized, client initialization canceled."
        )
        return
    guid = str(uuid4())
    fs_config.client = MarmotClientConfig(
        guid=validate_guid(
            guid
            if args.use_defaults
            else Prompt.ask("please enter marmot client guid", default=guid)
        ),
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
    fs_config.to_filepath(args.config)


async def _init_server(args):
    fs_config = MarmotConfig()
    if args.config.is_file():
        fs_config = MarmotConfig.from_filepath(args.config)
    if fs_config.server:
        LOGGER.warning(
            "server already initialized, server initialization canceled."
        )
        return
    fs_config.server = MarmotServerConfig(
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
    fs_config.to_filepath(args.config)


async def _show_client(args):
    fs_config = _load_client_config(args.config)
    pubkey = fs_config.client.prikey.public_key()
    table = Table(
        "Property",
        "Value",
        title="Marmot Client Config",
        box=ROUNDED,
        expand=True,
    )
    table.add_row("guid", fs_config.client.guid)
    table.add_row("url", str(fs_config.client.url))
    table.add_row("pubkey", dump_marmot_public_key(pubkey))
    CONSOLE.print(table)


async def _show_server(args):
    fs_config = _load_server_config(args.config)
    table = Table(
        "Property",
        "Value",
        title="Marmot Server Config",
        box=ROUNDED,
        expand=True,
    )
    table.add_row("host", fs_config.server.host)
    table.add_row("port", str(fs_config.server.port))
    table.add_row("redis.url", _redact_redis_url(fs_config.server.redis.url))
    table.add_row(
        "redis.max_connections", str(fs_config.server.redis.max_connections)
    )
    CONSOLE.print(table)
    table = Table(
        "GUID",
        "Public Key",
        title="Marmot Server Declared Clients",
        box=ROUNDED,
        expand=True,
    )
    for fs_guid, fs_pubkey in fs_config.server.clients.items():
        table.add_row(fs_guid, dump_marmot_public_key(fs_pubkey))
    CONSOLE.print(table)
    r_node = Tree("channels")
    for fs_name in sorted(fs_config.server.channels.keys()):
        fs_channel = fs_config.server.channels[fs_name]
        c_node = r_node.add(fs_name)
        l_node = c_node.add("listeners")
        for listener in fs_channel.listeners:
            l_node.add(listener)
        w_node = c_node.add("whistlers")
        for whistler in fs_channel.whistlers:
            w_node.add(whistler)
    CONSOLE.print(
        Panel(r_node, title="Marmot Server Declared Channels", box=ROUNDED)
    )


async def _add_client(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.add_client(args.guid, args.pubkey)
    fs_config.to_filepath(args.config)
    LOGGER.info("client added: %s", args.guid)


async def _del_client(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.del_client(args.guid)
    fs_config.to_filepath(args.config)
    LOGGER.info("client deleted: %s", args.guid)


async def _add_channel(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.add_channel(args.channel)
    fs_config.to_filepath(args.config)
    LOGGER.info("channel added: %s", args.channel)


async def _del_channel(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.del_channel(args.channel)
    fs_config.to_filepath(args.config)
    LOGGER.info("channel deleted: %s", args.channel)


async def _add_whistler(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.add_whistler(args.channel, args.guid)
    fs_config.to_filepath(args.config)
    LOGGER.info("whistler added: (%s, %s)", args.channel, args.guid)


async def _del_whistler(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.del_whistler(args.channel, args.guid)
    fs_config.to_filepath(args.config)
    LOGGER.info("whistler deleted: (%s, %s)", args.channel, args.guid)


async def _add_listener(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.add_listener(args.channel, args.guid)
    fs_config.to_filepath(args.config)
    LOGGER.info("listener added: (%s, %s)", args.channel, args.guid)


async def _del_listener(args):
    fs_config = _load_server_config(args.config)
    fs_config.server.del_listener(args.channel, args.guid)
    fs_config.to_filepath(args.config)
    LOGGER.info("listener deleted: (%s, %s)", args.channel, args.guid)


async def _diff(args):
    fs_config = _load_server_config(args.config)
    backend = MarmotServerBackend(
        args.redis_url or fs_config.server.redis.url,
        args.redis_max_connections or fs_config.server.redis.max_connections,
    )
    try:
        be_config = await backend.dump()
    finally:
        await backend.close()
    table = Table(
        "GUID",
        "Public Key",
        title="Marmot Server Declared Clients",
        box=ROUNDED,
        expand=True,
    )
    for be_guid, be_pubkey in be_config.server.clients.items():
        style = (
            DELETED_STYLE if be_guid not in fs_config.server.clients else None
        )
        table.add_row(be_guid, dump_marmot_public_key(be_pubkey), style=style)
    for fs_guid, fs_pubkey in fs_config.server.clients.items():
        if fs_guid in be_config.server.clients:
            continue
        table.add_row(
            fs_guid, dump_marmot_public_key(fs_pubkey), style=ADDED_STYLE
        )
    CONSOLE.print(table)
    r_node = Tree("channels")
    for be_name in sorted(be_config.server.channels.keys()):
        be_channel = be_config.server.channels[be_name]
        fs_channel = fs_config.server.channels.get(be_name)
        channel_style = DELETED_STYLE if not fs_channel else None
        c_node = r_node.add(Text(be_name, style=channel_style))
        l_node = c_node.add("listeners")
        for listener in be_channel.listeners:
            style = channel_style or (
                DELETED_STYLE if listener not in fs_channel.listeners else None
            )
            l_node.add(Text(listener, style=style))
        if fs_channel:
            for listener in fs_channel.listeners:
                if listener not in be_channel.listeners:
                    l_node.add(Text(listener, style=ADDED_STYLE))
        w_node = c_node.add("whistlers")
        for whistler in be_channel.whistlers:
            style = channel_style or (
                DELETED_STYLE if whistler not in fs_channel.whistlers else None
            )
            w_node.add(Text(whistler, style=style))
        if fs_channel:
            for whistler in fs_channel.whistlers:
                if whistler not in be_channel.whistlers:
                    w_node.add(Text(whistler, style=ADDED_STYLE))
    for fs_name in sorted(fs_config.server.channels.keys()):
        fs_channel = fs_config.server.channels[fs_name]
        if fs_name in be_config.server.channels:
            continue
        c_node = r_node.add(Text(fs_name, style=ADDED_STYLE))
        l_node = c_node.add("listeners")
        for listener in fs_channel.listeners:
            l_node.add(Text(listener, style=ADDED_STYLE))
        w_node = c_node.add("whistlers")
        for whistler in fs_channel.whistlers:
            w_node.add(Text(whistler, style=ADDED_STYLE))
    CONSOLE.print(
        Panel(r_node, title="Marmot Server Declared Channels", box=ROUNDED)
    )


async def _push(args):
    LOGGER.warning(
        "/!\\ changes made to fs config clients or channels will be published /!\\"
    )
    if not Confirm.ask("do you want to push config from fs to backend?"):
        return
    fs_config = _load_server_config(args.config)
    backend = MarmotServerBackend(
        args.redis_url or fs_config.server.redis.url,
        args.redis_max_connections or fs_config.server.redis.max_connections,
    )
    LOGGER.info("pushing config to backend...")
    try:
        await backend.load(fs_config)
    finally:
        await backend.close()
    LOGGER.info("push is complete.")


async def _pull(args):
    LOGGER.warning(
        "/!\\ changes made to fs config clients or channels will be lost /!\\"
    )
    if not Confirm.ask("do you want to pull config from backend to fs?"):
        return
    fs_config = _load_server_config(args.config)
    backend = MarmotServerBackend(
        args.redis_url or fs_config.server.redis.url,
        args.redis_max_connections or fs_config.server.redis.max_connections,
    )
    LOGGER.info("pulling config from backend...")
    try:
        be_config = await backend.dump()
    finally:
        await backend.close()
    fs_config.server.clients = be_config.server.clients
    fs_config.server.channels = be_config.server.channels
    fs_config.to_filepath(args.config)
    LOGGER.info("pull is complete.")


def _parse_args():
    parser = ArgumentParser(description=BANNER)
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=Path('marmot.json'),
        help="marmot configuration file",
    )
    cmd = parser.add_subparsers(dest='cmd')
    cmd.required = True
    init_client = cmd.add_parser(
        'init-client', help="initialize client configuration"
    )
    init_client.add_argument(
        '--use-defaults',
        action='store_true',
        help="use default values, non-interactive mode",
    )
    init_client.set_defaults(async_func=_init_client)
    init_server = cmd.add_parser(
        'init-server', help="initialize server configuration"
    )
    init_server.add_argument(
        '--use-defaults',
        action='store_true',
        help="use default values, non-interactive mode",
    )
    init_server.set_defaults(async_func=_init_server)
    show_client = cmd.add_parser(
        'show-client', help="show client configuration"
    )
    show_client.set_defaults(async_func=_show_client)
    show_server = cmd.add_parser(
        'show-server', help="show server configuration"
    )
    show_server.set_defaults(async_func=_show_server)
    add_client = cmd.add_parser('add-client', help="add a client")
    add_client.add_argument('guid', help="guid of the client to add")
    add_client.add_argument('pubkey', help="public key of the client to add")
    add_client.set_defaults(async_func=_add_client)
    del_client = cmd.add_parser('del-client', help="delete a client")
    del_client.add_argument('guid', help="guid of the client to delete")
    del_client.set_defaults(async_func=_del_client)
    add_channel = cmd.add_parser('add-channel', help="add a channel")
    add_channel.add_argument('channel', help="channel to add")
    add_channel.set_defaults(async_func=_add_channel)
    del_channel = cmd.add_parser('del-channel', help="delete a channel")
    del_channel.add_argument('channel', help="channel to delete")
    del_channel.set_defaults(async_func=_del_channel)
    add_whistler = cmd.add_parser(
        'add-whistler', help="add a whistler to a channel"
    )
    add_whistler.add_argument('channel', help="channel to update")
    add_whistler.add_argument('guid', help="guid of the whistler to add")
    add_whistler.set_defaults(async_func=_add_whistler)
    del_whistler = cmd.add_parser(
        'del-whistler', help="delete a whistler from a channel"
    )
    del_whistler.add_argument('channel', help="channel to update")
    del_whistler.add_argument('guid', help="guid of the whistler to delete")
    del_whistler.set_defaults(async_func=_del_whistler)
    add_listener = cmd.add_parser(
        'add-listener', help="add a listener to a channel"
    )
    add_listener.add_argument('channel', help="channel to update")
    add_listener.add_argument('guid', help="guid of the listener to add")
    add_listener.set_defaults(async_func=_add_listener)
    del_listener = cmd.add_parser(
        'del-listener', help="delete a listener from a channel"
    )
    del_listener.add_argument('channel', help="channel to update")
    del_listener.add_argument('guid', help="guid of the listener to delete")
    del_listener.set_defaults(async_func=_del_listener)
    diff = cmd.add_parser(
        'diff',
        help="show what will happen when fs config is pushed to backend",
    )
    diff.add_argument(
        '--redis-url',
        help="marmot redis url, do not add credentials in this url",
    )
    diff.add_argument(
        '--redis-max-connections',
        type=int,
        help="marmot redis max connections",
    )
    diff.set_defaults(async_func=_diff)
    push = cmd.add_parser('push', help="push fs config to backend")
    push.add_argument(
        '--redis-url',
        help="marmot redis url, do not add credentials in this url",
    )
    push.add_argument(
        '--redis-max-connections',
        type=int,
        help="marmot redis max connections",
    )
    push.set_defaults(async_func=_push)
    pull = cmd.add_parser('pull', help="pull backend config to fs")
    pull.add_argument(
        '--redis-url',
        help="marmot redis url, do not add credentials in this url",
    )
    pull.add_argument(
        '--redis-max-connections',
        type=int,
        help="marmot redis max connections",
    )
    pull.set_defaults(async_func=_pull)
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

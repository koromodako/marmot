#!/usr/bin/env python3
"""Generate test configuration
"""
from pathlib import Path
from argparse import ArgumentParser
from marmot.helper.crypto import generate_marmot_private_key
from marmot.helper.config import (
    MarmotConfig,
    MarmotServerConfig,
    MarmotClientConfig,
    MarmotChannelConfig,
    MarmotRedisConfig,
)
from marmot.helper.secret_provider import (
    SECRET_PROVIDER,
    SecretProviderBackend,
)

LISTENERS = 'l'
WHISTLERS = 'w'
CHANNELS = {
    'general': {
        LISTENERS: {'irc-forwarder'},
        WHISTLERS: {'service-a-whistler', 'service-b-whistler'},
    },
    'service-a': {
        LISTENERS: {'irc-forwarder', 'test'},
        WHISTLERS: {'service-a-whistler'},
    },
    'service-b': {
        LISTENERS: {'irc-forwarder', 'test'},
        WHISTLERS: {'service-b-whistler'},
    },
    'emergency': {
        LISTENERS: {'irc-forwarder', 'emergency-monitor'},
        WHISTLERS: {'service-a-whistler', 'service-b-whistler'},
    },
}


def _write_config(filepath: Path, fs_config: MarmotConfig):
    print(f"writing: {filepath}")
    fs_config.to_filepath(filepath)


def _create_client(args, guid: str):
    private_key = generate_marmot_private_key()
    fs_config = MarmotConfig(
        client=MarmotClientConfig(
            guid=guid,
            url='https://api.marmot.org',
            capath=(
                args.output_directory.parent / 'ssl' / 'marmot.ca.crt.pem'
            ),
            prikey=private_key,
        )
    )
    _write_config(args.output_directory / f'mc-{guid}.json', fs_config)
    return private_key.public_key()


def _parse_args():
    parser = ArgumentParser(
        description="Generate test certificate chain including test CA certificate"
    )
    parser.add_argument(
        '--output-directory',
        '-o',
        type=Path,
        default=Path('/tmp/marmot-testing/config'),
        help="Output directory",
    )
    return parser.parse_args()


def app():
    """Application entrypoint"""
    args = _parse_args()
    args.output_directory /= 'config'
    args.output_directory.mkdir(parents=True, exist_ok=True)
    SECRET_PROVIDER.select(SecretProviderBackend.GENPASS)
    clients = {}
    channels = {}
    for channel, members in CHANNELS.items():
        channels[channel] = MarmotChannelConfig()
        for listener in members[LISTENERS]:
            if listener not in clients:
                clients[listener] = _create_client(args, listener)
            channels[channel].listeners.add(listener)
        for whistler in members[WHISTLERS]:
            if whistler not in clients:
                clients[whistler] = _create_client(args, whistler)
            channels[channel].whistlers.add(whistler)
    fs_config = MarmotConfig(
        server=MarmotServerConfig(
            host='0.0.0.0',
            port=1758,
            redis=MarmotRedisConfig(
                url='redis://marmot-redis',
                max_connections=50,
            ),
            clients=clients,
            channels=channels,
        )
    )
    _write_config(args.output_directory / 'ms.json', fs_config)


if __name__ == '__main__':
    app()

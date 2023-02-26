"""Marmot authorization module
"""
from .crypto import hash_marmot_data, verify_marmot_data_digest
from .logging import LOGGER


def can_listen(config, guid, channel, signature):
    """Determine if marmot can listen"""
    pubkey = config.server.clients.get(guid)
    if not pubkey:
        LOGGER.error("unknown client: %s", guid)
        return False
    conf = config.server.channels.get(channel)
    if not conf:
        LOGGER.error("unknown channel: %s", channel)
        return False
    if guid not in conf.listeners:
        LOGGER.error("unknown channel listener: %s", guid)
        return False
    digest = hash_marmot_data(':'.join([guid, channel]).encode())
    if not verify_marmot_data_digest(pubkey, digest, signature):
        LOGGER.error("signature verification failed.")
        return False
    return True


def can_whistle(config, message):
    """Determine if marmot can whistle"""
    guid = message.whistler
    channel = message.channel
    pubkey = config.server.clients.get(guid)
    if not pubkey:
        LOGGER.error("unknown client: %s", guid)
        return False
    conf = config.server.channels.get(channel)
    if not conf:
        LOGGER.error("unknown channel: %s", channel)
        return False
    if guid not in conf.whistlers:
        LOGGER.error("unknown channel whistler: %s", guid)
        return False
    if not message.verify(pubkey):
        LOGGER.error("signature verification failed.")
        return False
    return True

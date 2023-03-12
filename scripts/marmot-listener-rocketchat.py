#!/usr/bin/env python3
"""Marmot listener script to forward messages in RocketChat channel
"""
from os import getenv
from pprint import pprint
from asyncio import new_event_loop
from aiohttp import ClientSession

# ----- BEGIN CONFIGURATION -----
ROCKETCHAT_BASE_URL = 'https://rocketchat.marmot.org'
ROCKETCHAT_POST_MSG_ENDPOINT = '/api/v1/chat.postMessage'
ROCKETCHAT_DEFAULT_CHANNEL = '#general'
MARMOT_ROCKETCHAT_LEVEL_MAPPING = {
# marmot level: rocketchat emoji
    'CRITICAL': ':bangbang:',
    'ERROR': ':exclamation:',
    'WARNING': ':warning:',
    'INFO': ':speech_balloon:',
    'DEBUG': ':thought_balloon:',
}
MARMOT_ROCKETCHAT_CHANNEL_MAPPING = {
# marmot channel: rocketchat channel
    'rocketchat': '#notification',
}
# ----- END   CONFIGURATION -----

# marmot environment variables
MARMOT_MSG_LEVEL = getenv('MARMOT_MSG_LEVEL')
MARMOT_MSG_CHANNEL = getenv('MARMOT_MSG_CHANNEL')
MARMOT_MSG_CONTENT = getenv('MARMOT_MSG_CONTENT')
MARMOT_MSG_WHISTLER = getenv('MARMOT_MSG_WHISTLER')
# rocketchat environment variables
ROCKETCHAT_USER_ID = getenv('ROCKETCHAT_USER_ID')
ROCKETCHAT_AUTH_TOKEN = getenv('ROCKETCHAT_AUTH_TOKEN')

async def _post_message(http_client):
    async with http_client.post(
        ROCKETCHAT_POST_MSG_ENDPOINT,
        json={
            'channel': MARMOT_ROCKETCHAT_CHANNEL_MAPPING.get(
                MARMOT_MSG_CHANNEL, ROCKETCHAT_DEFAULT_CHANNEL
            ),
            'emoji': MARMOT_ROCKETCHAT_LEVEL_MAPPING[MARMOT_MSG_LEVEL],
            'alias': MARMOT_MSG_WHISTLER,
            'text': MARMOT_MSG_CONTENT,
        },
    ) as response:
        body = await response.json()
        pprint(body)


async def _async_app():
    async with ClientSession(
        base_url=ROCKETCHAT_BASE_URL,
        headers={
            'X-User-Id': ROCKETCHAT_USER_ID,
            'X-Auth-Token': ROCKETCHAT_AUTH_TOKEN,
        },
        raise_for_status=True,
    ) as http_client:
        try:
            await _post_message(http_client)
        except:
            print("failed!")


def app():
    """Application entrypoint"""
    loop = new_event_loop()
    loop.run_until_complete(_async_app())
    loop.close()


if __name__ == '__main__':
    app()

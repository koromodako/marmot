#!/usr/bin/env python3
"""Marmot listener script to forward messages in Teams channel
"""
from os import getenv
from pprint import pprint
from asyncio import new_event_loop
from aiohttp import ClientSession

# ----- BEGIN CONFIGURATION -----
TEAMS_TEAM_ID = 'fbe2bf47-16c8-47cf-b4a5-4b9b187c508b'
TEAMS_BASE_URL = 'https://graph.microsoft.com/v1.0'
TEAMS_DEFAULT_CHANNEL = '19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2'
MARMOT_TEAMS_LEVEL_MAPPING = {
# marmot level: teams emoji
    'CRITICAL': 'urgent',
    'ERROR': 'high',
    'WARNING': 'high',
    'INFO': 'normal',
    'DEBUG': 'normal',
}
MARMOT_TEAMS_CHANNEL_MAPPING = {
# marmot channel: teams channel
    'teams': '19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2',
}
# ----- END   CONFIGURATION -----

# marmot environment variables
MARMOT_MSG_LEVEL = getenv('MARMOT_MSG_LEVEL')
MARMOT_MSG_CHANNEL = getenv('MARMOT_MSG_CHANNEL')
MARMOT_MSG_CONTENT = getenv('MARMOT_MSG_CONTENT')
MARMOT_MSG_WHISTLER = getenv('MARMOT_MSG_WHISTLER')
# teams environment variables
TEAMS_AUTH_TOKEN = getenv('TEAMS_AUTH_TOKEN')

async def _post_message(http_client):
    channel = MARMOT_TEAMS_CHANNEL_MAPPING.get(
        MARMOT_MSG_CHANNEL, TEAMS_DEFAULT_CHANNEL
    )
    teams_post_msg_endpoint = f'/teams/{TEAMS_TEAM_ID}/channels/{channel}/messages'
    async with http_client.post(
        teams_post_msg_endpoint,
        json={
          'body': {
            'content': MARMOT_MSG_CONTENT,
          },
          'subject': MARMOT_MSG_WHISTLER, # might not be the best field to use for this
          'importance': MARMOT_TEAMS_LEVEL_MAPPING[MARMOT_MSG_LEVEL],
        },
    ) as response:
        body = await response.json()
        pprint(body)


async def _async_app():
    async with ClientSession(
        base_url=TEAMS_BASE_URL,
        headers={
            'Authorization': f'Bearer {TEAMS_AUTH_TOKEN}',
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

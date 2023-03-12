#!/usr/bin/env python3
"""Marmot listener script to forward messages in Slack channel
"""
from os import getenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ----- BEGIN CONFIGURATION -----
SLACK_BASE_URL = 'https://slack.marmot.org'
SLACK_POST_MSG_ENDPOINT = '/api/chat.postMessage'
SLACK_DEFAULT_CHANNEL = 'C123456'
MARMOT_SLACK_LEVEL_MAPPING = {
# marmot level: slack emoji
    'CRITICAL': ':bangbang:',
    'ERROR': ':exclamation:',
    'WARNING': ':warning:',
    'INFO': ':speech_balloon:',
    'DEBUG': ':thought_balloon:',
}
MARMOT_SLACK_CHANNEL_MAPPING = {
# marmot channel: slack channel
    'slack': 'C123456',
}
# ----- END   CONFIGURATION -----

# marmot environment variables
MARMOT_MSG_LEVEL = getenv('MARMOT_MSG_LEVEL')
MARMOT_MSG_CHANNEL = getenv('MARMOT_MSG_CHANNEL')
MARMOT_MSG_CONTENT = getenv('MARMOT_MSG_CONTENT')
MARMOT_MSG_WHISTLER = getenv('MARMOT_MSG_WHISTLER')
# slack environment variables
SLACK_BOT_TOKEN = getenv('SLACK_BOT_TOKEN')


def app():
    """Application entrypoint"""
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        result = client.chat_postMessage(
            channel=MARMOT_SLACK_CHANNEL_MAPPING.get(
                MARMOT_MSG_CHANNEL, SLACK_DEFAULT_CHANNEL
            ),
            icon_emoji=MARMOT_SLACK_LEVEL_MAPPING[MARMOT_MSG_LEVEL],
            text=MARMOT_MSG_CONTENT,
            username=MARMOT_MSG_WHISTLER,
        )
        print(result)
    except SlackApiError:
        print("failed!")

if __name__ == '__main__':
    app()

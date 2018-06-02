#!/usr/bin/env python3
import argparse
import json
from slackclient import SlackClient

class Service:
    def __init__(self, slack_token):
        self.slack_token = slack_token
        self.client = SlackClient(slack_token)

    def emit(self, data):
        json_string = json.dumps(data)
        print(json_string)

    def load_auth(self):
        logged_user = self.client.api_call('auth.test')
        self.emit({
            'pyslack_type': 'auth',
            'url': logged_user['url'],
            'team': logged_user['team'],
            'user_id': logged_user['user_id'],
            'user': logged_user['user']
        })

    def load_channels(self):
        channels = self.client.api_call(
            'conversations.list',
            exclude_archived=True,
            types='public_channel,private_channel,im,mpim'
        )['channels']
        _channels = []
        for channel in channels:
            if ('is_channel' in channel
                and channel['is_member']
                and (channel['is_channel'] or not channel['is_mpim'])):
                _channels.append({
                    'id': channel['id'],
                    'name': channel['name'],
                    'is_private': channel['is_private'],
                    'topic': channel.get('topic'),
                })
        _channels.sort(key=lambda channel: channel['name'])
        self.emit({
            'pyslack_type': 'channels',
            'channels': _channels
        })

    def start(self):
        self.load_auth()
        self.load_channels()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='Slack Token')
    args = parser.parse_args()
    service = Service(args.token)
    service.start()

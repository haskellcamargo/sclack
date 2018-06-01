#!/usr/bin/env python3
import argparse
import json
from slackclient import SlackClient

parser = argparse.ArgumentParser()
parser.add_argument('--token', help='Slack Token')
args = parser.parse_args()

client = SlackClient(args.token)
logged_user = client.api_call('auth.test')
initial_data = {
    'pyslack_type': 'auth',
    'url': logged_user['url'],
    'team': logged_user['team'],
    'user_id': logged_user['user_id'],
    'user': logged_user['user']
}
print(json.dumps(initial_data))

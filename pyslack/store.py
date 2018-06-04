from slackclient import SlackClient

class State:
    pass

class Store:
    def __init__(self, slack_token):
        self.slack = SlackClient(slack_token)
        self.state = State()

    def load_auth(self):
        self.state.auth = self.slack.api_call('auth.test')

    def load_channels(self):
        all_channels = self.slack.api_call(
            'conversations.list',
            exclude_archived=True,
            types='public_channel,private_channel,im,mpim'
        )['channels']
        self.state.channels = list(filter(
            lambda channel: 'is_channel' in channel
                and channel['is_member']
                and (channel['is_channel'] or not channel['is_mpim']),
            all_channels
        ))
        self.state.channels.sort(key=lambda channel: channel['name'])

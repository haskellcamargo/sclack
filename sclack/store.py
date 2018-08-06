from slackclient import SlackClient

class State:
    def __init__(self):
        self.channels = []
        self.dms = []
        self.groups = []
        self.messages = []
        self.users = []
        self.pin_count = 0
        self.has_more = False
        self.is_limited = False
        self.profile_user_id = None
        self.bots = {}
        self.editing_widget = None
        self.last_date = None

class Cache:
    def __init__(self):
        self.avatar = {}
        self.picture = {}

class Store:
    def __init__(self, slack_token, config):
        self.slack_token = slack_token
        self.slack = SlackClient(slack_token)
        self.state = State()
        self.cache = Cache()
        self.config = config

    def find_user_by_id(self, user_id):
        return self._users_dict.get(user_id)

    def load_auth(self):
        self.state.auth = self.slack.api_call('auth.test')

    def find_or_load_bot(self, bot_id):
        if bot_id in self.state.bots:
            return self.state.bots[bot_id]
        request = self.slack.api_call('bots.info', bot=bot_id)
        if request['ok']:
            self.state.bots[bot_id] = request['bot']
            return self.state.bots[bot_id]

    def load_messages(self, channel_id):
        history = self.slack.api_call(
            'conversations.history',
            channel=channel_id
        )
        self.state.messages = history['messages']
        self.state.has_more = history.get('has_more', False)
        self.state.is_limited = history.get('is_limited', False)
        self.state.pin_count = history['pin_count']
        self.state.messages.reverse()

    def get_channel_info(self, channel_id):
        if channel_id[0] == 'G':
            return self.slack.api_call('groups.info', channel=channel_id)['group']
        elif channel_id[0] == 'C':
            return self.slack.api_call('channels.info', channel=channel_id)['channel']

    def load_channel(self, channel_id):
        if channel_id[0] in ('C', 'G'):
            self.state.channel = self.get_channel_info(channel_id)

    def load_channels(self):
        conversations = self.slack.api_call(
            'users.conversations',
            exclude_archived=True,
            types='public_channel,private_channel,im'
        )['channels']
        for channel in conversations:
            # Public channel
            if channel.get('is_channel', False):
                self.state.channels.append(channel)
            # Private channel
            elif channel.get('is_group', False):
                self.state.channels.append(channel)
            # Direct message
            elif channel.get('is_im', False) and not channel.get('is_user_deleted', False):
                self.state.dms.append(channel)
        self.state.channels.sort(key=lambda channel: channel['name'])
        self.state.dms.sort(key=lambda dm: dm['created'])

    def load_groups(self):
        self.state.groups = self.slack.api_call('mpim.list')['groups']

    def load_users(self):
        self.state.users = list(filter(
            lambda user: not user.get('deleted', False),
            self.slack.api_call('users.list')['members']
        ))
        self._users_dict = {}
        self._bots_dict = {}
        for user in self.state.users:
            if user.get('is_bot', False):
                self._users_dict[user['profile']['bot_id']] = user
            self._users_dict[user['id']] = user

    def set_topic(self, channel_id, topic):
        return self.slack.api_call('conversations.setTopic', channel=channel_id, topic=topic)

    def delete_message(self, channel_id, ts):
        return self.slack.api_call('chat.delete', channel=channel_id, ts=ts, as_user=True)

    def edit_message(self, channel_id, ts, text):
        return self.slack.api_call(
            'chat.update',
            channel=channel_id,
            ts=ts,
            as_user=True,
            link_names=True,
            text=text
        )

    def get_presence(self, user_id):
        return self.slack.api_call('users.getPresence', user=user_id)

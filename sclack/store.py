from slackclient import SlackClient


class State:
    def __init__(self):
        self.channels = []
        self.dms = []
        self.groups = []
        self.stars = []
        self.messages = []
        self.thread_messages = []
        self.users = []
        self.pin_count = 0
        self.has_more = False
        self.is_limited = False
        self.profile_user_id = None
        self.bots = {}
        self.editing_widget = None
        self.last_date = None
        self.did_render_new_messages = False
        self.online_users = set()
        self.is_snoozed = False


class Cache:
    def __init__(self):
        self.avatar = {}
        self.picture = {}


class Store:
    def __init__(self, workspaces, config):
        self.workspaces = workspaces
        slack_token = workspaces[0][1]
        self.slack_token = slack_token
        self.slack = SlackClient(slack_token)
        self.state = State()
        self.cache = Cache()
        self.config = config

    def switch_to_workspace(self, workspace_number):
        self.slack_token = self.workspaces[workspace_number - 1][1]
        self.slack.token = self.slack_token
        self.slack.server.token = self.slack_token
        self.state = State()
        self.cache = Cache()

    def find_user_by_id(self, user_id):
        return self._users_dict.get(user_id)

    def get_user_display_name(self, user_detail):
        """
        FIXME
        Get real name of user to display
        :param user_detail:
        :return:
        """
        if user_detail is None:
            return ''

        return user_detail.get('display_name') or user_detail.get('real_name') or user_detail['name']

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

    def load_thread_messages(self, channel_id, parent_ts):
        """
        Load all of the messages sent in reply to the message with the given timestamp.
        """
        original = self.slack.api_call(
            "conversations.history",
            channel=channel_id,
            latest=parent_ts,
            inclusive=True,
            limit=1
        )

        if len(original['messages']) > 0:
            self.state.thread_messages = original['messages']

    def is_valid_channel_id(self, channel_id):
        """
        Check whether channel_id is valid
        :param channel_id:
        :return:
        """
        return channel_id[0] in ('C', 'G', 'D')

    def is_channel(self, channel_id):
        """
        Is a channel
        :param channel_id:
        :return:
        """
        return channel_id[0] == 'C'

    def is_dm(self, channel_id):
        """
        Is direct message
        :param channel_id:
        :return:
        """
        return channel_id[0] == 'D'

    def is_group(self, channel_id):
        """
        Is a group
        :param channel_id:
        :return:
        """
        return channel_id[0] == 'G'

    def get_channel_info(self, channel_id):
        if channel_id[0] == 'G':
            return self.slack.api_call('groups.info', channel=channel_id)['group']
        elif channel_id[0] == 'C':
            return self.slack.api_call('conversations.info', channel=channel_id)['channel']
        elif channel_id[0] == 'D':
            return self.slack.api_call('im.info', channel=channel_id)['im']

    def get_channel_members(self, channel_id):
        return self.slack.api_call('conversations.members', channel=channel_id)

    def mark_read(self, channel_id, ts):
        if self.is_group(channel_id):
            return self.slack.api_call('groups.mark', channel=channel_id, ts=ts)
        elif self.is_channel(channel_id):
            return self.slack.api_call('channels.mark', channel=channel_id, ts=ts)
        elif self.is_dm(channel_id):
            return self.slack.api_call('im.mark', channel=channel_id, ts=ts)

    def get_permalink(self, channel_id, ts):
        # https://api.slack.com/methods/chat.getPermalink
        return self.slack.api_call('chat.getPermalink', channel=channel_id, message_ts=ts)

    def set_snooze(self, snoozed_time):
        return self.slack.api_call('dnd.setSnooze', num_minutes=snoozed_time)

    def load_channel(self, channel_id):
        if channel_id[0] in ('C', 'G', 'D'):
            self.state.channel = self.get_channel_info(channel_id)
            self.state.members = self.get_channel_members(channel_id)
            self.state.did_render_new_messages = self.state.channel.get('unread_count_display', 0) == 0

    def load_channels(self):
        conversations = self.slack.api_call(
            'users.conversations',
            exclude_archived=True,
            limit=1000,  # 1k is max limit
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

    def load_stars(self):
        """
        Load stars
        :return:
        """
        self.state.stars = list(filter(
            lambda star: star.get('type', '') in ('channel', 'im', 'group',),
            self.slack.api_call('stars.list')['items']
        ))

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

    def load_user_dnd(self):
        self.state.is_snoozed = self.slack.api_call('dnd.info').get('snooze_enabled')

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

    def post_message(self, channel_id, message):
        return self.slack.api_call(
            'chat.postMessage',
            channel=channel_id,
            as_user=True,
            link_names=True,
            text=message
        )

    def get_presence(self, user_id):
        response = self.slack.api_call('users.getPresence', user=user_id)

        if response.get('ok', False):
            if response['presence'] == 'active':
                self.state.online_users.add(user_id)
            else:
                self.state.online_users.discard(user_id)

        return response

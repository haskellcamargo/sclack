import asyncio
import contextlib

import urwid

from .slackcontrol import WebClient
from .utils.channel import is_channel, is_dm, is_group


class State:
    def __init__(self):
        self.auth = None
        self.channel = None
        self.channels = []
        self.dms = []
        self.groups = []
        self.stars = []
        self.members = None
        self.messages = []
        self.thread_messages = []
        self.thread_parent = None
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
        self.semaphore = asyncio.Semaphore(20)
        self.slack = WebClient(slack_token)
        self.urwid_mainloop = None
        self.state = State()
        self.cache = Cache()
        self.config = config
        self._users_dict = {}
        self._bots_dict = {}

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

        return (
            user_detail.get('display_name') or user_detail.get('real_name') or user_detail['name']
        )

    async def load_auth(self):
        async with self.semaphore:
            self.state.auth = await self.slack.auth_test()

    async def find_or_load_bot(self, bot_id):
        if bot_id in self.state.bots:
            return self.state.bots[bot_id]
        async with self.semaphore:
            request = await self.slack.bots_info(bot=bot_id)
        if request['ok']:
            self.state.bots[bot_id] = request['bot']
            return self.state.bots[bot_id]

    async def load_messages(self, channel_id):
        async with self.semaphore:
            history = await self.slack.conversations_history(channel=channel_id)
        self.state.messages = history['messages']
        self.state.has_more = history.get('has_more', False)
        self.state.is_limited = history.get('is_limited', False)
        self.state.pin_count = history['pin_count']
        self.state.messages.reverse()

    async def load_thread_messages(self, channel_id, parent_ts):
        """
        Load all of the messages sent in reply to the message with the given timestamp.
        """
        async with self.semaphore:
            replies = await self.slack.conversations_replies(channel=channel_id, ts=parent_ts,)
        self.state.thread_messages = replies['messages']
        self.state.has_more = replies.get('has_more', False)

    async def get_channel_info(self, channel_id):
        if is_group(channel_id):
            async with self.semaphore:
                info = await self.slack.groups_info(channel=channel_id)
            return info['group']
        elif is_channel(channel_id):
            async with self.semaphore:
                info = await self.slack.channels_info(channel=channel_id)
            return info['channel']
        elif is_dm(channel_id):
            async with self.semaphore:
                info = await self.slack.im_info(channel=channel_id)
            return info['im']

    async def get_channel_members(self, channel_id):
        async with self.semaphore:
            return await self.slack.api_call('conversations.members', channel=channel_id)

    async def mark_read(self, channel_id, ts):
        if is_group(channel_id):
            async with self.semaphore:
                return await self.slack.groups_mark(channel=channel_id, ts=ts)
        elif is_channel(channel_id):
            async with self.semaphore:
                return await self.slack.channels_mark(channel=channel_id, ts=ts)
        elif is_dm(channel_id):
            async with self.semaphore:
                return await self.slack.im_mark(channel=channel_id, ts=ts)

    async def get_permalink(self, channel_id, ts):
        # https://api.slack.com/methods/chat.getPermalink
        async with self.semaphore:
            return await self.slack.chat_getPermalink(channel=channel_id, message_ts=ts)

    async def set_snooze(self, snoozed_time):
        async with self.semaphore:
            return await self.slack.dnd_setSnooze(num_minutes=snoozed_time)

    async def load_channel(self, channel_id):
        if channel_id[0] in ('C', 'G', 'D'):
            self.state.channel, self.state.members = await asyncio.gather(
                self.get_channel_info(channel_id), self.get_channel_members(channel_id)
            )
            self.state.did_render_new_messages = (
                self.state.channel.get('unread_count_display', 0) == 0
            )

    async def load_channels(self):
        async with self.semaphore:
            conversations = await self.slack.users_conversations(
                exclude_archived=True,
                limit=1000,  # 1k is max limit
                types='public_channel,private_channel,im,mpim',
            )
        for channel in conversations['channels']:
            # Public channel
            if channel.get('is_channel', False):
                self.state.channels.append(channel)
            # Private channel
            elif channel.get('is_group', False):
                self.state.channels.append(channel)
            # Multiple conversations
            elif channel.get('is_mpim', False):
                c_name = f'[{channel["name"][5:-2].replace("--",", ")}]'
                channel['name_normalized'] = c_name
                self.state.channels.append(channel)
            # Direct message
            elif channel.get('is_im', False) and not channel.get('is_user_deleted', False):
                self.state.dms.append(channel)
        self.state.channels.sort(
            key=lambda channel: (not channel['is_general'], channel['is_mpim'], channel['name'])
        )
        self.state.dms.sort(key=lambda dm: dm['created'])

    def get_channel_name(self, channel_id):
        matched_channel = None

        for channel in self.state.channels:
            if channel['id'] == channel_id:
                matched_channel = channel
                break

        if matched_channel:
            return matched_channel['name']

        return channel_id

    async def load_groups(self):
        async with self.semaphore:
            result = await self.slack.mpim_list()
        self.state.groups = result['groups']

    async def load_stars(self):
        """
        Load stars
        :return:
        """
        async with self.semaphore:
            stars = await self.slack.stars_list()
        self.state.stars = list(
            filter(
                lambda star: star.get('type', '') in ('channel', 'im', 'group',), stars['items'],
            )
        )

    async def load_users(self):
        async with self.semaphore:
            users = await self.slack.users_list()
        self.state.users = list(
            filter(lambda user: not user.get('deleted', False), users['members'],)
        )
        self._users_dict.clear()
        self._bots_dict.clear()
        for user in self.state.users:
            if user.get('is_bot', False):
                self._users_dict[user['profile']['bot_id']] = user
            self._users_dict[user['id']] = user

    async def load_user_dnd(self):
        async with self.semaphore:
            info = await self.slack.dnd_info()
        self.state.is_snoozed = info.get('snooze_enabled')

    async def set_topic(self, channel_id, topic):
        async with self.semaphore:
            return await self.slack.conversations_setTopic(channel=channel_id, topic=topic)

    async def delete_message(self, channel_id, ts):
        async with self.semaphore:
            return await self.slack.chat_delete(channel=channel_id, ts=ts, as_user=True)

    async def edit_message(self, channel_id, ts, text):
        async with self.semaphore:
            return await self.slack.chat_update(
                channel=channel_id, ts=ts, as_user=True, link_names=True, text=text
            )

    async def post_message(self, channel_id, message):
        async with self.semaphore:
            return await self.slack.chat_postMessage(
                channel=channel_id, as_user=True, link_names=True, text=message
            )

    async def post_thread_message(self, channel_id, parent_ts, message):
        async with self.semaphore:
            return await self.slack.chat_postMessage(
                channel=channel_id, as_user=True, link_name=True, text=message, thread_ts=parent_ts,
            )

    async def get_presence(self, user_id):
        async with self.semaphore:
            response = await self.slack.users_getPresence(user=user_id)
        if response.get('ok', False):
            if response['presence'] == 'active':
                self.state.online_users.add(user_id)
            else:
                self.state.online_users.discard(user_id)
        return response

    def make_urwid_mainloop(self, body, palette, event_loop, unhandled_input):
        self.urwid_mainloop = urwid.MainLoop(
            body, palette=palette, event_loop=event_loop, unhandled_input=unhandled_input
        )
        return self.urwid_mainloop

    @contextlib.contextmanager
    def interrupt_urwid_mainloop(self):
        self.urwid_mainloop.stop()
        self.urwid_mainloop.screen.stop()
        try:
            yield
        finally:
            self.urwid_mainloop.screen.start()
            self.urwid_mainloop.start()

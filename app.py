#!/usr/bin/env python3
import asyncio
import concurrent.futures
import functools
import json
import os
import requests
import sys
import time
import traceback
import tempfile
import urwid
from datetime import datetime
from sclack.components import Attachment, Channel, ChannelHeader, ChatBox, Dm
from sclack.components import Indicators, MarkdownText, MessageBox
from sclack.component.message import Message
from sclack.components import NewMessagesDivider, Profile, ProfileSideBar
from sclack.components import Reaction, SideBar, TextDivider
from sclack.components import User, Workspaces
from sclack.image import Image
from sclack.loading import LoadingChatBox, LoadingSideBar
from sclack.quick_switcher import QuickSwitcher
from sclack.store import Store
from sclack.themes import themes

from sclack.widgets.set_snooze import SetSnoozeWidget
from sclack.utils.channel import is_dm, is_group, is_channel

loop = asyncio.get_event_loop()

SCLACK_SUBTYPE = 'sclack_message'
MARK_READ_ALARM_PERIOD = 3


class SclackEventLoop(urwid.AsyncioEventLoop):
    def run(self):
        self._loop.set_exception_handler(self._custom_exception_handler)
        self._loop.run_forever()

    def set_exception_handler(self, handler):
        self._custom_exception_handler = handler


class App:
    message_box = None

    def _exception_handler(self, loop, context):
        try:
            exception = context.get('exception')
            if not exception:
                raise Exception
            message = 'Whoops, something went wrong:\n\n' + str(exception) + '\n' + ''.join(traceback.format_tb(exception.__traceback__))
            self.chatbox = LoadingChatBox(message)
        except Exception as exc:
            self.chatbox = LoadingChatBox('Unable to show exception: ' + str(exc))
        return

    def __init__(self, config):
        self._loading = False
        self.config = config
        self.quick_switcher = None
        self.set_snooze_widget = None
        self.workspaces = list(config['workspaces'].items())
        self.store = Store(self.workspaces, self.config)
        Store.instance = self.store
        urwid.set_encoding('UTF-8')
        sidebar = LoadingSideBar()
        chatbox = LoadingChatBox('Everything is terrible!')
        palette = themes.get(config['theme'], themes['default'])

        custom_loop = SclackEventLoop(loop=loop)
        custom_loop.set_exception_handler(self._exception_handler)

        if len(self.workspaces) <= 1:
            self.workspaces_line = None
        else:
            self.workspaces_line = Workspaces(self.workspaces)

        self.columns = urwid.Columns([
            ('fixed', config['sidebar']['width'], urwid.AttrWrap(sidebar, 'sidebar')),
            urwid.AttrWrap(chatbox, 'chatbox')
        ])
        self._body = urwid.Frame(self.columns, header=self.workspaces_line)

        self.urwid_loop = urwid.MainLoop(
            self._body,
            palette=palette,
            event_loop=custom_loop,
            unhandled_input=self.unhandled_input
        )
        self.configure_screen(self.urwid_loop.screen)
        self.last_keypress = (0, None)

    def start(self):
        self._loading = True
        loop.create_task(self.animate_loading())
        loop.create_task(self.component_did_mount())
        self.urwid_loop.run()

    def switch_to_workspace(self, workspace_number):
        if not self._loading:
            self._loading = True
            self.sidebar = LoadingSideBar()
            self.chatbox = LoadingChatBox('And it becomes worse!')
            self.message_box = None
            self.store.switch_to_workspace(workspace_number)
            loop.create_task(self.animate_loading())
            loop.create_task(self.component_did_mount())

    @property
    def is_chatbox_rendered(self):
        return not self._loading and self.chatbox and type(self.chatbox) is ChatBox

    @property
    def sidebar(self):
        return self.columns.contents[0][0].original_widget

    @sidebar.setter
    def sidebar(self, sidebar):
        self.columns.contents[0][0].original_widget = sidebar

    @property
    def chatbox(self):
        return self.columns.contents[1][0].original_widget

    @chatbox.setter
    def chatbox(self, chatbox):
        self.columns.contents[1][0].original_widget = chatbox

    @asyncio.coroutine
    def animate_loading(self):
        def update(*args):
            if self._loading:
                self.chatbox.circular_loading.next_frame()
                self.urwid_loop.set_alarm_in(0.2, update)
        update()

    @asyncio.coroutine
    def component_did_mount(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            yield from self.mount_sidebar(executor)
            yield from self.mount_chatbox(executor, self.store.state.channels[0]['id'])

    @asyncio.coroutine
    def mount_sidebar(self, executor):
        yield from asyncio.gather(
            loop.run_in_executor(executor, self.store.load_auth),
            loop.run_in_executor(executor, self.store.load_channels),
            loop.run_in_executor(executor, self.store.load_stars),
            loop.run_in_executor(executor, self.store.load_groups),
            loop.run_in_executor(executor, self.store.load_users),
            loop.run_in_executor(executor, self.store.load_user_dnd),
        )
        profile = Profile(name=self.store.state.auth['user'], is_snoozed=self.store.state.is_snoozed)

        channels = []
        dms = []
        stars = []
        star_user_tmp = []  # To contain user, channel should be on top of list
        stars_user_id = []  # To ignore item in DMs list
        stars_channel_id = []  # To ignore item in channels list
        max_users_sidebar = self.store.config['sidebar']['max_users']

        # Prepare list of Star users and channels
        for dm in self.store.state.stars:
            if is_dm(dm['channel']):
                detail = self.store.get_channel_info(dm['channel'])
                user = self.store.find_user_by_id(detail['user'])

                if user:
                    stars_user_id.append(user['id'])
                    star_user_tmp.append(Dm(
                        dm['channel'],
                        name=self.store.get_user_display_name(user),
                        user=user['id'],
                        you=False
                    ))
            elif is_channel(dm['channel']) or is_group(dm['channel']):
                channel = self.store.get_channel_info(dm['channel'])
                # Group chat (is_mpim) is not supported, prefer to https://github.com/haskellcamargo/sclack/issues/67
                if channel and not channel.get('is_archived', False) and not channel.get('is_mpim', False):
                    stars_channel_id.append(channel['id'])
                    stars.append(Channel(
                        id=channel['id'],
                        name=channel['name'],
                        is_private=channel.get('is_private', True)
                    ))
        stars.extend(star_user_tmp)

        # Prepare list of Channels
        for channel in self.store.state.channels:
            if channel['id'] in stars_channel_id:
                continue
            channels.append(Channel(
                id=channel['id'],
                name=channel['name'],
                is_private=channel['is_private']
            ))

        # Prepare list of DM
        dm_users = self.store.state.dms[:max_users_sidebar]
        for dm in dm_users:
            if dm['user'] in stars_user_id:
                continue
            user = self.store.find_user_by_id(dm['user'])
            if user:
                dms.append(Dm(
                    dm['id'],
                    name=self.store.get_user_display_name(user),
                    user=dm['user'],
                    you=user['id'] == self.store.state.auth['user_id']
                ))

        self.sidebar = SideBar(profile, channels, dms, stars=stars, title=self.store.state.auth['team'])
        urwid.connect_signal(self.sidebar, 'go_to_channel', self.go_to_channel)
        loop.create_task(self.get_channels_info(executor, self.sidebar.get_all_channels()))
        loop.create_task(self.get_presences(executor, self.sidebar.get_all_dms()))
        loop.create_task(self.get_dms_unread(executor, self.sidebar.get_all_dms()))

    @asyncio.coroutine
    def get_presences(self, executor, dm_widgets):
        """
        Compute and return presence because updating UI from another thread is unsafe
        :param executor:
        :param dm_widgets:
        :return:
        """
        def get_presence(dm_widget):
            presence = self.store.get_presence(dm_widget.user)
            return [dm_widget, presence]
        presences = yield from asyncio.gather(*[
            loop.run_in_executor(executor, get_presence, dm_widget)
            for dm_widget in dm_widgets
        ])

        for presence in presences:
            [widget, response] = presence
            if response['ok']:
                widget.set_presence(response['presence'])

    @asyncio.coroutine
    def get_dms_unread(self, executor, dm_widgets):
        """
        Compute and return unread_count_display because updating UI from another thread is unsafe
        :param executor:
        :param dm_widgets:
        :return:
        """
        def get_presence(dm_widget):
            profile_response = self.store.get_channel_info(dm_widget.id)
            return [dm_widget, profile_response]

        responses = yield from asyncio.gather(*[
            loop.run_in_executor(executor, get_presence, dm_widget)
            for dm_widget in dm_widgets
        ])

        for profile_response in responses:
            [widget, response] = profile_response
            if response is not None:
                widget.set_unread(response['unread_count_display'])

    @asyncio.coroutine
    def get_channels_info(self, executor, channels):
        def get_info(channel):
            info = self.store.get_channel_info(channel.id)
            return [channel, info]
        channels_info = yield from asyncio.gather(*[
            loop.run_in_executor(executor, get_info, channel)
            for channel in channels
        ])

        for channel_info in channels_info:
            [widget, response] = channel_info
            widget.set_unread(response.get('unread_count_display', 0))

    @asyncio.coroutine
    def update_chat(self, event):
        """
        Update channel/DM message count badge
        :param event:
        :return:
        """
        self.sidebar.update_items(event)

    @asyncio.coroutine
    def mount_chatbox(self, executor, channel):
        yield from asyncio.gather(
            loop.run_in_executor(executor, self.store.load_channel, channel),
            loop.run_in_executor(executor, self.store.load_messages, channel)
        )
        messages = self.render_messages(self.store.state.messages)
        header = self.render_chatbox_header()
        self._loading = False
        self.sidebar.select_channel(channel)
        self.message_box = MessageBox(
            user=self.store.state.auth['user'],
            is_read_only=self.store.state.channel.get('is_read_only', False)
        )
        self.chatbox = ChatBox(messages, header, self.message_box, self.urwid_loop)
        urwid.connect_signal(self.chatbox, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(self.chatbox, 'mark_read', self.handle_mark_read)
        urwid.connect_signal(self.chatbox, 'open_quick_switcher', self.open_quick_switcher)
        urwid.connect_signal(self.chatbox, 'open_set_snooze', self.open_set_snooze)

        urwid.connect_signal(self.message_box.prompt_widget, 'submit_message', self.submit_message)
        urwid.connect_signal(self.message_box.prompt_widget, 'go_to_last_message', self.go_to_last_message)

        self.real_time_task = loop.create_task(self.start_real_time())

    def edit_message(self, widget, user_id, ts, original_text):
        is_logged_user = self.store.state.auth['user_id'] == user_id
        current_date = datetime.today()
        message_date = datetime.fromtimestamp(float(ts))
        # Only messages sent in the last 5 minutes can be edited
        if is_logged_user and (current_date - message_date).total_seconds() < 60 * 5:
            self.store.state.editing_widget = widget
            self.set_insert_mode()
            self.chatbox.message_box.text = original_text
            widget.set_edit_mode()

    def get_permalink(self, widget, channel_id, ts):
        try:
            permalink = self.store.get_permalink(channel_id, ts)
            if permalink and permalink.get('permalink'):
                text = permalink.get('permalink')
                self.set_insert_mode()
                self.chatbox.message_box.text = text
        except:
            pass

    def delete_message(self, widget, user_id, ts):
        if self.store.state.auth['user_id'] == user_id:
            if self.store.delete_message(self.store.state.channel['id'], ts)['ok']:
                self.chatbox.body.body.remove(widget)

    def go_to_profile(self, user_id):
        if len(self.columns.contents) > 2:
            self.columns.contents.pop()
        if user_id == self.store.state.profile_user_id:
            self.store.state.profile_user_id = None
        else:
            user = self.store.find_user_by_id(user_id)
            if not user:
                return
            self.store.state.profile_user_id = user_id
            profile = ProfileSideBar(
                user.get('display_name') or user.get('real_name') or user['name'],
                user['profile'].get('status_text', None),
                user['profile'].get('tz_label', None),
                user['profile'].get('phone', None),
                user['profile'].get('email', None),
                user['profile'].get('skype', None)
            )
            if self.config['features']['pictures']:
                loop.create_task(self.load_profile_avatar(user['profile'].get('image_512'), profile))
            self.columns.contents.append((profile, ('given', 35, False)))

    def render_chatbox_header(self):

        if self.store.state.channel['id'][0] == 'D':
            user = self.store.find_user_by_id(self.store.state.channel['user'])
            header = ChannelHeader(
                name=user.get('display_name') or user.get('real_name') or user['name'],
                topic=user['profile']['status_text'],
                is_starred=self.store.state.channel.get('is_starred', False),
                is_dm_workaround_please_remove_me=True
            )
        else:
            header = ChannelHeader(
                name=self.store.state.channel['name'],
                topic=self.store.state.channel['topic']['value'],
                num_members=len(self.store.state.channel['members']),
                pin_count=self.store.state.pin_count,
                is_private=self.store.state.channel.get('is_group', False),
                is_starred=self.store.state.channel.get('is_starred', False)
            )
            urwid.connect_signal(header.topic_widget, 'done', self.on_change_topic)
        return header

    def on_change_topic(self, text):
        self.chatbox.header.original_topic = text
        self.store.set_topic(self.store.state.channel['id'], text)
        self.go_to_sidebar()

    def render_message(self, message, channel_id=None):
        is_app = False
        subtype = message.get('subtype')

        if subtype == SCLACK_SUBTYPE:
            message = Message(
                message['ts'],
                '',
                User('1', 'sclack'),
                MarkdownText(message['text']),
                Indicators(False, False)
            )
            urwid.connect_signal(message, 'go_to_sidebar', self.go_to_sidebar)
            urwid.connect_signal(message, 'quit_application', self.quit_application)
            urwid.connect_signal(message, 'set_insert_mode', self.set_insert_mode)
            urwid.connect_signal(message, 'mark_read', self.handle_mark_read)

            return message

        message_text = message['text']
        files = message.get('files', [])

        # Files uploaded
        if len(files) > 0:
            file_links = ['"{}" <{}>'.format(file.get('title'), file.get('url_private')) for file in message.get('files')]
            file_upload_text = 'File{} uploaded'.format('' if len(files) == 1 else 's')
            file_text = '{} {}'.format(file_upload_text ,', '.join(file_links))

            if message_text == '':
                message_text = file_text
            else:
                message_text = '{}\n{}'.format(message_text, file_text)

        if subtype == 'bot_message':
            bot = (self.store.find_user_by_id(message['bot_id'])
                or self.store.find_or_load_bot(message['bot_id']))
            if bot:
                user_id = message['bot_id']
                user_name = bot.get('profile', {}).get('display_name') or bot.get('name')
                color = bot.get('color')
                is_app = 'app_id' in bot
            else:
                return None
        elif subtype == 'file_comment':
            user = self.store.find_user_by_id(message['comment']['user'])

            # A temporary fix for a null pointer exception for truncated or deleted users
            if user is None:
                return None

            user_id = user['id']
            user_name = user['profile']['display_name'] or user.get('name')
            color = user.get('color')
            if message.get('file'):
                message['file'] = None
        else:
            user = self.store.find_user_by_id(message['user'])

            # A temporary fix for a null pointer exception for truncated or deleted users
            if user is None:
                return None

            user_id = user['id']
            user_name = user['profile']['display_name'] or user.get('name')
            color = user.get('color')

        user = User(user_id, user_name, color, is_app)
        text = MarkdownText(message_text)
        indicators = Indicators('edited' in message, message.get('is_starred', False))
        reactions = [
            Reaction(reaction['name'], reaction['count'])
            for reaction in message.get('reactions', [])
        ]

        attachments = []
        for attachment in message.get('attachments', []):
            attachment_widget = Attachment(
                service_name=attachment.get('service_name'),
                title=attachment.get('title'),
                from_url=attachment.get('from_url'),
                fields=attachment.get('fields'),
                color=attachment.get('color'),
                author_name=attachment.get('author_name') or attachment.get('author_subname'),
                pretext=attachment.get('pretext'),
                text=message_text,
                attachment_text=attachment.get('text'),
                ts=attachment.get('ts'),
                footer=attachment.get('footer')
            )
            image_url = attachment.get('image_url')
            if image_url and self.config['features']['pictures']:
                loop.create_task(self.load_picture_async(
                    image_url,
                    attachment.get('image_width', 500),
                    attachment_widget,
                    auth=False
                ))
            attachments.append(attachment_widget)

        file = message.get('file')

        if file:
            files.append(file)

        message_channel = channel_id if channel_id is not None else message.get('channel')

        message = Message(
            message['ts'],
            message_channel,
            user,
            text,
            indicators,
            attachments=attachments,
            reactions=reactions
        )

        self.lazy_load_images(files, message)

        urwid.connect_signal(message, 'edit_message', self.edit_message)
        urwid.connect_signal(message, 'get_permalink', self.get_permalink)
        urwid.connect_signal(message, 'go_to_profile', self.go_to_profile)
        urwid.connect_signal(message, 'go_to_sidebar', self.go_to_sidebar)
        urwid.connect_signal(message, 'delete_message', self.delete_message)
        urwid.connect_signal(message, 'quit_application', self.quit_application)
        urwid.connect_signal(message, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(message, 'mark_read', self.handle_mark_read)

        return message

    def lazy_load_images(self, files, widget):
        """
        Load images lazily and attache to widget
        :param files:
        :param widget:
        :return:
        """
        if not self.config['features']['pictures']:
            return

        allowed_file_types = ('bmp', 'gif', 'jpeg', 'jpg', 'png')

        for file in files:
            if file.get('filetype') in allowed_file_types:
                loop.create_task(self.load_picture_async(
                    file['url_private'],
                    file.get('original_w', 500),
                    widget,
                    not file.get('is_external', True)
                ))

    def render_messages(self, messages, channel_id=None):
        _messages = []
        previous_date = self.store.state.last_date
        last_read_datetime = datetime.fromtimestamp(float(self.store.state.channel.get('last_read', '0')))
        today = datetime.today().date()
        for message in messages:
            message_datetime = datetime.fromtimestamp(float(message['ts']))
            message_date = message_datetime.date()
            date_text = None
            unread_text = None
            if not previous_date or previous_date != message_date:
                previous_date = message_date
                self.store.state.last_date = previous_date
                if message_date == today:
                    date_text = 'Today'
                else:
                    date_text = message_date.strftime('%A, %B %d')

            # New messages badge
            if (message_datetime > last_read_datetime and not self.store.state.did_render_new_messages
                and (self.store.state.channel.get('unread_count_display', 0) > 0)):
                self.store.state.did_render_new_messages = True
                unread_text = 'new messages'
            if unread_text is not None:
                _messages.append(NewMessagesDivider(unread_text, date=date_text))
            elif date_text is not None:
                _messages.append(TextDivider(('history_date', date_text), 'center'))

            message = self.render_message(message, channel_id)

            if message is not None:
                _messages.append(message)

        return _messages

    def handle_mark_read(self, data):
        """
        Mark as read to bottom
        :return:
        """
        row_index = data if data is not None else -1

        def read(*kwargs):
            loop.create_task(
                self.mark_read_slack(row_index)
            )

        now = time.time()
        if now - self.last_keypress[0] < MARK_READ_ALARM_PERIOD and self.last_keypress[1] is not None:
            self.urwid_loop.remove_alarm(self.last_keypress[1])

        self.last_keypress = (now, self.urwid_loop.set_alarm_in(MARK_READ_ALARM_PERIOD, read))

    def scroll_messages(self, *args):
        index = self.chatbox.body.scroll_to_new_messages()
        loop.create_task(
            self.mark_read_slack(index)
        )

    @asyncio.coroutine
    def mark_read_slack(self, index):
        if not self.is_chatbox_rendered:
            return

        if index is None or index == -1:
            index = len(self.chatbox.body.body) - 1

        if len(self.chatbox.body.body) > index:
            message = self.chatbox.body.body[index]

            # Only apply for message
            if not hasattr(message, 'channel_id'):
                if len(self.chatbox.body.body) > index + 1:
                    message = self.chatbox.body.body[index + 1]
                else:
                    message = self.chatbox.body.body[index - 1]

            if message.channel_id:
                self.store.mark_read(message.channel_id, message.ts)

    @asyncio.coroutine
    def _go_to_channel(self, channel_id):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            yield from asyncio.gather(
                loop.run_in_executor(executor, self.store.load_channel, channel_id),
                loop.run_in_executor(executor, self.store.load_messages, channel_id)
            )
            self.store.state.last_date = None

            if len(self.store.state.messages) == 0:
                messages = self.render_messages([{
                    'text': "There's no conversation in this channel",
                    'ts': '0',
                    'subtype': SCLACK_SUBTYPE,
                }])
            else:
                messages = self.render_messages(self.store.state.messages, channel_id=channel_id)

            header = self.render_chatbox_header()
            if self.is_chatbox_rendered:
                self.chatbox.body.body[:] = messages
                self.chatbox.header = header
                self.chatbox.message_box.is_read_only = self.store.state.channel.get('is_read_only', False)
                self.sidebar.select_channel(channel_id)
                self.urwid_loop.set_alarm_in(0, self.scroll_messages)

            if len(self.store.state.messages) == 0:
                self.go_to_sidebar()
            else:
                self.go_to_chatbox()

    def go_to_channel(self, channel_id):
        if self.quick_switcher:
            urwid.disconnect_signal(self.quick_switcher, 'go_to_channel', self.go_to_channel)
            self.urwid_loop.widget = self._body
            self.quick_switcher = None
        loop.create_task(self._go_to_channel(channel_id))

    def handle_set_snooze_time(self, snoozed_time):
        loop.create_task(self.dispatch_snooze_time(snoozed_time))

    def handle_close_set_snooze(self):
        """
        Close set_snooze
        :return:
        """
        if self.set_snooze_widget:
            urwid.disconnect_signal(self.set_snooze_widget, 'set_snooze_time', self.handle_set_snooze_time)
            urwid.disconnect_signal(self.set_snooze_widget, 'close_set_snooze', self.handle_close_set_snooze)
            self.urwid_loop.widget = self._body
            self.set_snooze_widget = None

    @asyncio.coroutine
    def dispatch_snooze_time(self, snoozed_time):
        self.store.set_snooze(snoozed_time)

    @asyncio.coroutine
    def load_picture_async(self, url, width, message_widget, auth=True):
        width = min(width, 800)
        bytes_in_cache = self.store.cache.picture.get(url)
        if bytes_in_cache:
            message_widget.file = bytes_in_cache
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            headers = {}
            if auth:
                headers = {'Authorization': 'Bearer {}'.format(self.store.slack_token)}
            bytes = yield from loop.run_in_executor(
                executor,
                functools.partial(requests.get, url, headers=headers)
            )
            file = tempfile.NamedTemporaryFile(delete=False)
            file.write(bytes.content)
            file.close()
            picture = Image(file.name, width=(width / 10))
            message_widget.file = picture

    @asyncio.coroutine
    def load_profile_avatar(self, url, profile):
        bytes_in_cache = self.store.cache.avatar.get(url)
        if bytes_in_cache:
            profile.avatar = bytes_in_cache
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            bytes = yield from loop.run_in_executor(executor, requests.get, url)
            file = tempfile.NamedTemporaryFile(delete=False)
            file.write(bytes.content)
            file.close()
            avatar = Image(file.name, width=35)
            self.store.cache.avatar[url] = avatar
            profile.avatar = avatar

    @asyncio.coroutine
    def start_real_time(self):
        self.store.slack.rtm_connect(auto_reconnect=True)

        def stop_typing(*args):
            # Prevent error while switching workspace
            if self.is_chatbox_rendered:
                self.chatbox.message_box.typing = None

        alarm = None

        while self.store.slack.server.connected is True:
            events = self.store.slack.rtm_read()

            for event in events:
                if event.get('type') == 'hello':
                    pass
                elif event.get('type') in ('channel_marked', 'group_marked', 'im_marked'):
                    unread = event.get('unread_count_display', 0)

                    if event.get('type') == 'channel_marked':
                        targets = self.sidebar.get_all_channels()
                    elif event.get('type') == 'group_marked':
                        targets = self.sidebar.get_all_groups()
                    else:
                        targets = self.sidebar.get_all_dms()

                    for target in targets:
                        if target.id == event['channel']:
                            target.set_unread(unread)

                elif event['type'] == 'message':
                    loop.create_task(
                        self.update_chat(event)
                    )

                    if event.get('channel') == self.store.state.channel['id']:
                        if not self.is_chatbox_rendered:
                            return

                        if event.get('subtype') == 'message_deleted':
                            for widget in self.chatbox.body.body:
                                if hasattr(widget, 'ts') and getattr(widget, 'ts') == event['deleted_ts']:
                                    self.chatbox.body.body.remove(widget)
                                    break
                        elif event.get('subtype') == 'message_changed':
                            for index, widget in enumerate(self.chatbox.body.body):
                                if hasattr(widget, 'ts') and getattr(widget, 'ts') == event['message']['ts']:
                                    self.chatbox.body.body[index] = self.render_message(event['message'])
                                    break
                        else:
                            self.chatbox.body.body.extend(self.render_messages([event]))
                            self.chatbox.body.scroll_to_bottom()
                    else:
                        pass
                elif event['type'] == 'user_typing':
                    if not self.is_chatbox_rendered:
                        return

                    if event.get('channel') == self.store.state.channel['id']:
                        user = self.store.find_user_by_id(event['user'])
                        name = user.get('display_name') or user.get('real_name') or user['name']
                        if alarm is not None:
                            self.urwid_loop.remove_alarm(alarm)
                        self.chatbox.message_box.typing = name
                        self.urwid_loop.set_alarm_in(3, stop_typing)
                    else:
                        pass
                        # print(json.dumps(event, indent=2))
                elif event.get('type') == 'dnd_updated' and 'dnd_status' in event:
                    self.store.is_snoozed = event['dnd_status']['snooze_enabled']
                    self.sidebar.profile.set_snooze(self.store.is_snoozed)
                elif event.get('ok', False):
                    if not self.is_chatbox_rendered:
                        return

                    # Message was sent, Slack confirmed it.
                    self.chatbox.body.body.extend(self.render_messages([{
                        'text': event['text'],
                        'ts': event['ts'],
                        'user': self.store.state.auth['user_id']
                    }]))
                    self.chatbox.body.scroll_to_bottom()
                    self.handle_mark_read(-1)
                else:
                    pass
                    # print(json.dumps(event, indent=2))
            yield from asyncio.sleep(0.5)

    def set_insert_mode(self):
        self.columns.focus_position = 1
        self.chatbox.focus_position = 'footer'
        self.message_box.focus_position = 1

    def set_edit_topic_mode(self):
        self.columns.focus_position = 1
        self.chatbox.focus_position = 'header'
        self.chatbox.header.go_to_end_of_topic()

    def go_to_chatbox(self):
        self.columns.focus_position = 1
        self.chatbox.focus_position = 'body'

    def leave_edit_mode(self):
        if self.store.state.editing_widget:
            self.store.state.editing_widget.unset_edit_mode()
            self.store.state.editing_widget = None
        self.chatbox.message_box.text = ''

    def go_to_sidebar(self):
        if len(self.columns.contents) > 2:
            self.columns.contents.pop()
        self.columns.focus_position = 0

        if self.store.state.editing_widget:
            self.leave_edit_mode()

        if self.quick_switcher:
            urwid.disconnect_signal(self.quick_switcher, 'go_to_channel', self.go_to_channel)
            self.urwid_loop.widget = self._body
            self.quick_switcher = None

    def submit_message(self, message):
        if self.store.state.editing_widget:
            channel = self.store.state.channel['id']
            ts = self.store.state.editing_widget.ts
            edit_result = self.store.edit_message(channel, ts, message)
            if edit_result['ok']:
                self.store.state.editing_widget.original_text = edit_result['text']
                self.store.state.editing_widget.set_text(MarkdownText(edit_result['text']))
            self.leave_edit_mode()
        else:
            channel = self.store.state.channel['id']
            if message.strip() != '':
                self.store.post_message(channel, message)
                self.leave_edit_mode()

    def go_to_last_message(self):
        self.go_to_chatbox()
        self.chatbox.body.go_to_last_message()

    def unhandled_input(self, key):
        """
        Handle shortcut key press
        :param key:
        :return:
        """
        keymap = self.store.config['keymap']

        if key == keymap['go_to_chatbox'] or key == keymap['cursor_right'] and self.message_box:
            return self.go_to_chatbox()
        elif key == keymap['go_to_sidebar']:
            return self.go_to_sidebar()
        elif key == keymap['quit_application']:
            return self.quit_application()
        elif key == keymap['set_edit_topic_mode'] and self.message_box and not self.store.state.channel['id'][0] == 'D':
            return self.set_edit_topic_mode()
        elif key == keymap['set_insert_mode'] and self.message_box:
            return self.set_insert_mode()
        elif key == keymap['open_quick_switcher']:
            return self.open_quick_switcher()
        elif key in ('1', '2', '3', '4', '5', '6', '7', '8', '9') and len(self.workspaces) >= int(key):
            # Loading or only 1 workspace
            if self._loading or self.workspaces_line is None:
                return

            # Workspace is selected
            selected_workspace = int(key)
            if selected_workspace - 1 == self.workspaces_line.selected:
                return
            self.workspaces_line.select(selected_workspace)

            # Stop rtm to switch workspace
            self.real_time_task.cancel()
            return self.switch_to_workspace(selected_workspace)
        elif key == keymap['set_snooze']:
            return self.open_set_snooze()

    def open_quick_switcher(self):
        if not self.quick_switcher:
            self.quick_switcher = QuickSwitcher(self.urwid_loop.widget, self.urwid_loop)
            urwid.connect_signal(self.quick_switcher, 'go_to_channel', self.go_to_channel)
            self.urwid_loop.widget = self.quick_switcher

    def open_set_snooze(self):
        if not self.set_snooze_widget:
            self.set_snooze_widget = SetSnoozeWidget(self.urwid_loop.widget, self.urwid_loop)
            urwid.connect_signal(self.set_snooze_widget, 'set_snooze_time', self.handle_set_snooze_time)
            urwid.connect_signal(self.set_snooze_widget, 'close_set_snooze', self.handle_close_set_snooze)
            self.urwid_loop.widget = self.set_snooze_widget

    def configure_screen(self, screen):
        screen.set_terminal_properties(colors=self.store.config['colors'])
        screen.set_mouse_tracking()
        if self.workspaces_line is not None:
            urwid.connect_signal(self.workspaces_line, 'switch_workspace', self.switch_to_workspace)

    def quit_application(self):
        self.urwid_loop.stop()
        if hasattr(self, 'real_time_task'):
            self.real_time_task.cancel()
        sys.exit()


def ask_for_token(json_config):
    if os.path.isfile(os.path.expanduser('~/.sclack')):
        with open(os.path.expanduser('~/.sclack'), 'r') as user_file:
            # Compatible with legacy configuration file
            new_config = json.load(user_file)
            if not 'workspaces' in new_config:
                new_config['workspaces'] = {'default': new_config['token']}
            json_config.update(new_config)
    else:
        print('There is no ~/.sclack file. Let\'s create one!')
        token = input('What is your Slack workspace token? ')
        with open(os.path.expanduser('~/.sclack'), 'w') as config_file:
            token_config = {'workspaces': {'default': token}}
            config_file.write(json.dumps(token_config, indent=False))
            json_config.update(token_config)

if __name__ == '__main__':
    json_config = {}
    with open('./config.json', 'r') as config_file:
        json_config.update(json.load(config_file))
    ask_for_token(json_config)
    app = App(json_config)
    app.start()

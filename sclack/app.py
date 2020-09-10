#!/usr/bin/env python3
import asyncio
import concurrent.futures
import functools
import json
import logging.config
import os
import re
import sys
import tempfile
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import requests
import urwid
import yaml

from . import slackcontrol
from .component.message import Message
from .components import (
    Attachment,
    Channel,
    ChannelHeader,
    ChatBox,
    Dm,
    Indicators,
    MarkdownText,
    MessageBox,
    NewMessagesDivider,
    Profile,
    ProfileSideBar,
    Reaction,
    SideBar,
    TextDivider,
    User,
    Workspaces,
)
from .image import Image
from .loading import LoadingChatBox, LoadingSideBar
from .notification import notify
from .quick_switcher import QuickSwitcher
from .store import Store
from .themes import themes
from .utils.channel import is_channel, is_dm, is_group
from .utils.message import get_mentioned_patterns
from .widgets.set_snooze import SetSnoozeWidget

loop = asyncio.get_event_loop()

SCLACK_SUBTYPE = 'sclack_message'
MARK_READ_ALARM_PERIOD = 3


def mpim_normalized_name(channel_name):
    return f'[{channel_name[5:-2].replace("--",", ")}]'


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
            message = (
                'Whoops, something went wrong:\n\n'
                + str(exception)
                + '\n'
                + ''.join(traceback.format_tb(exception.__traceback__))
            )
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
        self.showing_thread = False
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

        self.columns = urwid.Columns(
            [
                ('fixed', config['sidebar']['width'], urwid.AttrWrap(sidebar, 'sidebar')),
                urwid.AttrWrap(chatbox, 'chatbox'),
            ]
        )
        self._body = urwid.Frame(self.columns, header=self.workspaces_line)

        self.urwid_loop = self.store.make_urwid_mainloop(
            self._body,
            palette=palette,
            event_loop=custom_loop,
            unhandled_input=self.unhandled_input,
        )
        self.configure_screen(self.urwid_loop.screen)
        self.last_keypress = (0, None)
        self.mentioned_patterns = None

    def get_mentioned_patterns(self):
        return get_mentioned_patterns(self.store.state.auth['user_id'])

    def should_notify_me(self, message_obj):
        """
        Checking whether notify to user
        :param message_obj:
        :return:
        """
        # Snoozzzzzed or disabled
        if self.store.state.is_snoozed or self.config['features']['notification'] in ('', 'none'):
            return False

        # You send message, don't need notification
        if message_obj.get('user') == self.store.state.auth['user_id']:
            return False

        if self.config['features']['notification'] == 'all':
            return True

        # Private message
        if message_obj.get('channel') is not None and message_obj.get('channel')[0] == 'D':
            return True

        regex = self.mentioned_patterns
        if regex is None:
            regex = self.get_mentioned_patterns()
            self.mentioned_patterns = regex

        return len(re.findall(regex, message_obj['text'])) > 0

    @property
    def sidebar_column(self):
        return self.columns.contents[0]

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

    async def animate_loading(self):
        def update(*args):
            if self._loading:
                self.chatbox.circular_loading.next_frame()
                self.urwid_loop.set_alarm_in(0.2, update)

        update()

    async def component_did_mount(self):
        await self.mount_sidebar()
        await self.mount_chatbox(self.store.state.channels[0]['id']),
        await asyncio.gather(
            self.get_channels_info(self.sidebar.get_all_channels()),
            self.get_presences(self.sidebar.get_all_dms()),
            self.get_dms_unread(self.sidebar.get_all_dms()),
        )

    async def mount_sidebar(self):
        await asyncio.gather(
            self.store.load_auth(),
            self.store.load_channels(),
            self.store.load_stars(),
            self.store.load_groups(),
            self.store.load_users(),
            self.store.load_user_dnd(),
        )
        self.mentioned_patterns = self.get_mentioned_patterns()

        profile = Profile(
            name=self.store.state.auth['user'], is_snoozed=self.store.state.is_snoozed
        )

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
                detail = await self.store.get_channel_info(dm['channel'])
                user = self.store.find_user_by_id(detail['user'])

                if user:
                    stars_user_id.append(user['id'])
                    star_user_tmp.append(
                        Dm(
                            dm['channel'],
                            name=self.store.get_user_display_name(user),
                            user=user['id'],
                            you=False,
                        )
                    )
            elif is_channel(dm['channel']) or is_group(dm['channel']):
                channel = await self.store.get_channel_info(dm['channel'])
                # Group chat (is_mpim) is not supported, prefer to https://github.com/haskellcamargo/sclack/issues/67
                if (
                    channel
                    and not channel.get('is_archived', False)
                    and not channel.get('is_mpim', False)
                ):
                    stars_channel_id.append(channel['id'])
                    stars.append(
                        Channel(
                            id=channel['id'],
                            name=channel['name'],
                            is_private=channel.get('is_private', True),
                        )
                    )
        stars.extend(star_user_tmp)

        # Prepare list of Channels
        for channel in self.store.state.channels:
            if channel['is_mpim']:  # Handle the names of multiple dms
                channel['name'] = mpim_normalized_name(channel['name'])
            if channel['id'] in stars_channel_id:
                continue
            channels.append(
                Channel(id=channel['id'], name=channel['name'], is_private=channel['is_private'])
            )

        # Prepare list of DM
        dm_users = self.store.state.dms[:max_users_sidebar]
        for dm in dm_users:
            if dm['user'] in stars_user_id:
                continue
            user = self.store.find_user_by_id(dm['user'])
            if user:
                dms.append(
                    Dm(
                        dm['id'],
                        name=self.store.get_user_display_name(user),
                        user=dm['user'],
                        you=user['id'] == self.store.state.auth['user_id'],
                    )
                )

        self.sidebar = SideBar(
            profile, channels, dms, stars=stars, title=self.store.state.auth['team']
        )
        urwid.connect_signal(self.sidebar, 'go_to_channel', self.go_to_channel)

    async def get_presences(self, dm_widgets):
        """
        Compute and return presence because updating UI from another thread is unsafe
        :param dm_widgets:
        :return:
        """

        async def get_presence(dm_widget):
            presence = await self.store.get_presence(dm_widget.user)
            return [dm_widget, presence]

        presences = await asyncio.gather(*(get_presence(dm_widget) for dm_widget in dm_widgets))

        for presence in presences:
            [widget, response] = presence
            if response['ok']:
                widget.set_presence(response['presence'])

    async def get_dms_unread(self, dm_widgets):
        """
        Compute and return unread_count_display because updating UI from another thread is unsafe
        :param dm_widgets:
        :return:
        """

        async def get_presence(dm_widget):
            profile_response = await self.store.get_channel_info(dm_widget.id)
            return [dm_widget, profile_response]

        responses = await asyncio.gather(*(get_presence(dm_widget) for dm_widget in dm_widgets))

        for profile_response in responses:
            [widget, response] = profile_response
            if response is not None:
                widget.set_unread(response['unread_count_display'])

    async def get_channels_info(self, channels):
        async def get_info(channel):
            info = await self.store.get_channel_info(channel.id)
            return [channel, info]

        channels_info = await asyncio.gather(*(get_info(channel) for channel in channels))

        for channel_info in channels_info:
            [widget, response] = channel_info
            widget.set_unread(response.get('unread_count_display', 0))

    async def update_chat(self, channel_id):
        """
        Update channel/DM message count badge
        :param event:
        :return:
        """
        channel_info = await self.store.get_channel_info(channel_id)
        self.sidebar.update_items(channel_id, channel_info.get('unread_count_display', 0))

    async def mount_chatbox(self, channel):
        await asyncio.gather(
            self.store.load_channel(channel), self.store.load_messages(channel),
        )
        messages = await self.render_messages(self.store.state.messages, channel_id=channel)
        header = self.render_chatbox_header()
        self._loading = False
        self.sidebar.select_channel(channel)
        self.message_box = MessageBox(
            user=self.store.state.auth['user'],
            is_read_only=self.store.state.channel.get('is_read_only', False),
            users=[user['name'] for user in self.store.state.users],
        )
        self.chatbox = ChatBox(messages, header, self.message_box, self.urwid_loop)
        urwid.connect_signal(self.chatbox, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(self.chatbox, 'mark_read', self.handle_mark_read)
        urwid.connect_signal(self.chatbox, 'open_quick_switcher', self.open_quick_switcher)
        urwid.connect_signal(self.chatbox, 'open_set_snooze', self.open_set_snooze)

        async_connect_signal(self.message_box.prompt_widget, 'submit_message', self.submit_message)
        urwid.connect_signal(
            self.message_box.prompt_widget, 'go_to_last_message', self.go_to_last_message
        )

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

    async def get_permalink(self, widget, channel_id, ts):
        try:
            permalink = await self.store.get_permalink(channel_id, ts)
            if permalink and permalink.get('permalink'):
                text = permalink.get('permalink')
                self.set_insert_mode()
                self.chatbox.message_box.text = text
        except:
            pass

    async def delete_message(self, widget, user_id, ts):
        if self.store.state.auth['user_id'] == user_id:
            result = await self.store.delete_message(self.store.state.channel['id'], ts)
            if result['ok']:
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
                self.store.get_user_display_name(user),
                user['profile'].get('status_text', None),
                user['profile'].get('tz_label', None),
                user['profile'].get('phone', None),
                user['profile'].get('email', None),
                user['profile'].get('skype', None),
            )
            if self.config['features']['pictures']:
                loop.create_task(
                    self.load_profile_avatar(user['profile'].get('image_512'), profile)
                )
            self.columns.contents.append((profile, ('given', 35, False)))

    def render_chatbox_header(self):
        if self.store.state.channel['id'][0] == 'D':
            user = self.store.find_user_by_id(self.store.state.channel['user'])
            header = ChannelHeader(
                name=self.store.get_user_display_name(user),
                topic=user['profile']['status_text'],
                is_starred=self.store.state.channel.get('is_starred', False),
                is_dm_workaround_please_remove_me=True,
            )
        else:
            if self.store.state.channel['is_mpim']:
                channel_name = mpim_normalized_name(self.store.state.channel['name'])
            else:
                channel_name = self.store.state.channel['name']
            are_more_members = False
            if self.store.state.members.get('response_metadata', None):
                if self.store.state.members['response_metadata'].get('next_cursor', None):
                    are_more_members = True
            header = ChannelHeader(
                name=channel_name,
                topic=self.store.state.channel['topic']['value'],
                num_members=len(self.store.state.members['members']),
                more_members=are_more_members,
                pin_count=self.store.state.pin_count,
                is_private=self.store.state.channel.get('is_group', False),
                is_starred=self.store.state.channel.get('is_starred', False),
            )
            async_connect_signal(header.topic_widget, 'done', self.on_change_topic)
        return header

    async def on_change_topic(self, text):
        self.chatbox.header.original_topic = text
        await self.store.set_topic(self.store.state.channel['id'], text)
        self.go_to_sidebar()

    async def render_message(self, message, channel_id=None):
        is_app = False
        subtype = message.get('subtype')

        if subtype == SCLACK_SUBTYPE:
            message = Message(
                message['ts'],
                '',
                User('1', 'sclack'),
                MarkdownText(message['text']),
                Indicators(False, False),
            )
            urwid.connect_signal(message, 'go_to_sidebar', self.go_to_sidebar)
            urwid.connect_signal(message, 'quit_application', self.quit_application)
            urwid.connect_signal(message, 'set_insert_mode', self.set_insert_mode)
            urwid.connect_signal(message, 'mark_read', self.handle_mark_read)

            return message

        message_text = message.get('text', '')
        files = message.get('files', [])

        # Files uploaded
        if len(files) > 0:
            file_links = [
                '"{}" <{}>'.format(file.get('title'), file.get('url_private'))
                for file in message.get('files')
            ]
            file_upload_text = 'File{} uploaded'.format('' if len(files) == 1 else 's')
            file_text = '{} {}'.format(file_upload_text, ', '.join(file_links))

            if message_text == '':
                message_text = file_text
            else:
                message_text = '{}\n{}'.format(message_text, file_text)

        if subtype == 'bot_message':
            user_id = message['bot_id']
            bot = self.store.find_user_by_id(user_id)
            if not bot:
                bot = await self.store.find_or_load_bot(user_id)
            if bot:
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

        responses = message.get('replies', [])

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
                footer=attachment.get('footer'),
            )
            image_url = attachment.get('image_url')
            if image_url and self.config['features']['pictures']:
                loop.create_task(
                    self.load_picture_async(
                        image_url, attachment.get('image_width', 500), attachment_widget, auth=False
                    )
                )
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
            reactions=reactions,
            responses=responses,
        )

        self.lazy_load_images(files, message)

        urwid.connect_signal(message, 'edit_message', self.edit_message)
        async_connect_signal(message, 'get_permalink', self.get_permalink)
        urwid.connect_signal(message, 'go_to_profile', self.go_to_profile)
        urwid.connect_signal(message, 'go_to_sidebar', self.go_to_sidebar)
        async_connect_signal(message, 'delete_message', self.delete_message)
        urwid.connect_signal(message, 'quit_application', self.quit_application)
        urwid.connect_signal(message, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(message, 'open_in_browser', self.open_in_browser)
        urwid.connect_signal(message, 'mark_read', self.handle_mark_read)
        urwid.connect_signal(message, 'toggle_thread', self.toggle_thread)

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
                loop.create_task(
                    self.load_picture_async(
                        file['url_private'],
                        file.get('original_w', 500),
                        widget,
                        not file.get('is_external', True),
                    )
                )

    async def render_messages(self, messages, channel_id=None):
        _messages = []
        previous_date = self.store.state.last_date
        last_read_datetime = datetime.fromtimestamp(
            float(self.store.state.channel.get('last_read', '0'))
        )
        today = datetime.today().date()

        # If we are viewing a thread, add a dummy 'message' to indicate this
        # to the user.
        if self.showing_thread:
            _messages.append(
                await self.render_message(
                    {'text': "VIEWING THREAD", 'ts': '0', 'subtype': SCLACK_SUBTYPE,}
                )
            )

        for raw_message in messages:
            message_datetime = datetime.fromtimestamp(float(raw_message['ts']))
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
            if (
                message_datetime > last_read_datetime
                and not self.store.state.did_render_new_messages
                and (self.store.state.channel.get('unread_count_display', 0) > 0)
            ):
                self.store.state.did_render_new_messages = True
                unread_text = 'new messages'
            if unread_text is not None:
                _messages.append(NewMessagesDivider(unread_text, date=date_text))
            elif date_text is not None:
                _messages.append(TextDivider(('history_date', date_text), 'center'))

            message = await self.render_message(raw_message, channel_id)

            if message is not None:
                _messages.append(message)

        return _messages

    async def notify_message(self, channel_id, text, user=None):
        markdown_text = str(MarkdownText(text))
        user = self.store.find_user_by_id(user)
        sender_name = self.store.get_user_display_name(user)
        team = self.store.state.auth['team']
        notification_title = f'New message in {team}'
        if channel_id[0] != 'D':
            notification_title += ' #%s' % self.store.get_channel_name(channel_id)
        await notify(markdown_text, notification_title, sender_name)

    def handle_mark_read(self, data):
        """
        Mark as read to bottom
        :return:
        """
        row_index = data if data is not None else -1

        def read(*kwargs):
            loop.create_task(self.mark_read_slack(row_index))

        now = time.time()
        if (
            now - self.last_keypress[0] < MARK_READ_ALARM_PERIOD
            and self.last_keypress[1] is not None
        ):
            self.urwid_loop.remove_alarm(self.last_keypress[1])

        self.last_keypress = (now, self.urwid_loop.set_alarm_in(MARK_READ_ALARM_PERIOD, read))

    def open_in_browser(self, link):
        browser_name = self.store.config['features']['browser']
        browser_instance = webbrowser if browser_name == '' else webbrowser.get(browser_name)
        with self.store.interrupt_urwid_mainloop():
            browser_instance.open(link, new=2)

    def scroll_messages(self, *args):
        index = self.chatbox.body.scroll_to_new_messages()
        loop.create_task(self.mark_read_slack(index))

    async def mark_read_slack(self, index):
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
                await self.store.mark_read(message.channel_id, message.ts)

    async def _go_to_channel(self, channel_id):
        await asyncio.gather(
            self.store.load_channel(channel_id), self.store.load_messages(channel_id),
        )
        self.store.state.last_date = None

        if len(self.store.state.messages) == 0:
            messages = await self.render_messages(
                [
                    {
                        'text': "There's no conversation in this channel",
                        'ts': '0',
                        'subtype': SCLACK_SUBTYPE,
                    }
                ]
            )
        else:
            messages = await self.render_messages(self.store.state.messages, channel_id=channel_id)

        header = self.render_chatbox_header()
        if self.is_chatbox_rendered:
            self.chatbox.body.body[:] = messages
            self.chatbox.header = header
            self.chatbox.message_box.is_read_only = self.store.state.channel.get(
                'is_read_only', False
            )
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

        # We are not showing a thread - this needs to be reset as this method might be
        # triggered from the sidebar while a thread is being shown.
        self.showing_thread = False

        # Show the channel in the chatbox
        loop.create_task(self._go_to_channel(channel_id))

    async def _show_thread(self, channel_id, parent_ts):
        """
        Display the requested thread in the chatbox
        """
        await self.store.load_thread_messages(channel_id, parent_ts)
        self.store.state.last_date = None

        if len(self.store.state.thread_messages) == 0:
            messages = await self.render_messages(
                [
                    {
                        'text': "There was an error showing this thread :(",
                        'ts': '0',
                        'subtype': SCLACK_SUBTYPE,
                    }
                ]
            )
        else:
            messages = await self.render_messages(
                self.store.state.thread_messages, channel_id=channel_id
            )

        header = self.render_chatbox_header()
        if self.is_chatbox_rendered:
            self.chatbox.body.body[:] = messages
            self.chatbox.header = header
            self.chatbox.message_box.is_read_only = self.store.state.channel.get(
                'is_read_only', False
            )
            self.sidebar.select_channel(channel_id)
            self.urwid_loop.set_alarm_in(0, self.scroll_messages)

        if len(self.store.state.messages) == 0:
            self.go_to_sidebar()
        else:
            self.go_to_chatbox()

    def toggle_thread(self, channel_id, parent_ts):
        if self.showing_thread:
            # Currently showing a thread, return to the main channel
            self.showing_thread = False
            loop.create_task(self._go_to_channel(channel_id))
        else:
            # Show the chosen thread
            self.showing_thread = True
            self.store.state.thread_parent = parent_ts
            loop.create_task(self._show_thread(channel_id, parent_ts))

    def handle_set_snooze_time(self, snoozed_time):
        loop.create_task(self.store.set_snooze(snoozed_time))

    def handle_close_set_snooze(self):
        """
        Close set_snooze
        :return:
        """
        if self.set_snooze_widget:
            urwid.disconnect_signal(
                self.set_snooze_widget, 'set_snooze_time', self.handle_set_snooze_time
            )
            urwid.disconnect_signal(
                self.set_snooze_widget, 'close_set_snooze', self.handle_close_set_snooze
            )
            self.urwid_loop.widget = self._body
            self.set_snooze_widget = None

    async def load_picture_async(self, url, width, message_widget, auth=True):
        width = min(width, 800)
        bytes_in_cache = self.store.cache.picture.get(url)
        if bytes_in_cache:
            message_widget.file = bytes_in_cache
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            headers = {}
            if auth:
                headers = {'Authorization': 'Bearer {}'.format(self.store.slack_token)}
            bytes = await loop.run_in_executor(
                executor, functools.partial(requests.get, url, headers=headers)
            )
            file = tempfile.NamedTemporaryFile(delete=False)
            file.write(bytes.content)
            file.close()
            picture = Image(file.name, width=(width / 10))
            message_widget.file = picture

    async def load_profile_avatar(self, url, profile):
        bytes_in_cache = self.store.cache.avatar.get(url)
        if bytes_in_cache:
            profile.avatar = bytes_in_cache
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            bytes = await loop.run_in_executor(executor, requests.get, url)
            file = tempfile.NamedTemporaryFile(delete=False)
            file.write(bytes.content)
            file.close()
            avatar = Image(file.name, width=35)
            self.store.cache.avatar[url] = avatar
            profile.avatar = avatar

    async def start_real_time(self):
        await slackcontrol.RTMClient(self, token=self.store.slack_token)

    def stop_typing(self, *args):
        # Prevent error while switching workspace
        if self.is_chatbox_rendered:
            self.chatbox.message_box.typing = None

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

    async def submit_message(self, message):
        if not message.strip():
            return
        channel = self.store.state.channel['id']
        if self.store.state.editing_widget:
            ts = self.store.state.editing_widget.ts
            edit_result = await self.store.edit_message(channel, ts, message)
            if edit_result['ok']:
                self.store.state.editing_widget.original_text = edit_result['text']
                self.store.state.editing_widget.set_text(MarkdownText(edit_result['text']))
            self.leave_edit_mode()
        elif self.showing_thread:
            await self.store.post_thread_message(channel, self.store.state.thread_parent, message)
            self.leave_edit_mode()
            # Refresh the thread to make sure the new message immediately shows up
            loop.create_task(self._show_thread(channel, self.store.state.thread_parent))
        else:
            await self.store.post_message(channel, message)
            self.leave_edit_mode()
            # Refresh the channel to make sure the new message shows up
            loop.create_task(self._go_to_channel(channel))

    def go_to_last_message(self):
        self.go_to_chatbox()
        self.chatbox.body.go_to_last_message()

    @property
    def sidebar_width(self):
        return self.sidebar_column[1][1]

    def set_sidebar_width(self, newwidth):
        column, options = self.sidebar_column
        new_options = (options[0], newwidth, options[2])
        self.columns.contents[0] = (column, new_options)

    def hide_sidebar(self):
        self.set_sidebar_width(0)

    def show_sidebar(self):
        self.set_sidebar_width(self.config['sidebar']['width'])

    def toggle_sidebar(self):
        if self.sidebar_width > 0:
            self.hide_sidebar()
        else:
            self.show_sidebar()

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
        elif (
            key == keymap['set_edit_topic_mode']
            and self.message_box
            and not self.store.state.channel['id'][0] == 'D'
        ):
            return self.set_edit_topic_mode()
        elif key == keymap['set_insert_mode'] and self.message_box:
            return self.set_insert_mode()
        elif key == keymap['open_quick_switcher']:
            return self.open_quick_switcher()
        elif key in ('1', '2', '3', '4', '5', '6', '7', '8', '9') and len(self.workspaces) >= int(
            key
        ):
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
        elif key == keymap['toggle_sidebar']:
            return self.toggle_sidebar()

    def open_quick_switcher(self):
        if not self.quick_switcher:
            self.quick_switcher = QuickSwitcher(self.urwid_loop.widget, self.urwid_loop)
            urwid.connect_signal(self.quick_switcher, 'go_to_channel', self.go_to_channel)
            self.urwid_loop.widget = self.quick_switcher

    def open_set_snooze(self):
        if not self.set_snooze_widget:
            self.set_snooze_widget = SetSnoozeWidget(self.urwid_loop.widget, self.urwid_loop)
            urwid.connect_signal(
                self.set_snooze_widget, 'set_snooze_time', self.handle_set_snooze_time
            )
            urwid.connect_signal(
                self.set_snooze_widget, 'close_set_snooze', self.handle_close_set_snooze
            )
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


def load_configuration():
    filepath = Path(__file__).parent / 'resources' / 'config.yaml'

    with open(filepath) as config_file:
        json_config = yaml.load(config_file, Loader=yaml.FullLoader)

    filepath = Path('~/.sclack').expanduser()
    config_dir = Path(os.environ.get('XDG_CONFIG_HOME') or '~/.config').expanduser() / 'sclack'

    if not filepath.exists():
        filepath = config_dir / 'config.json'

    if not filepath.exists():
        filepath = config_dir / 'config.yaml'

    if not filepath.exists():
        ask_for_token(json_config)
        if not config_dir.exists():
            filepath.parent.mkdir(parents=True)
        with filepath.open('w') as config_file:
            if filepath.suffix == '.json':
                json.dump(json_config, config_file, indent=2)
            elif filepath.suffix == '.yaml':
                yaml.dump(json_config, config_file)
    else:
        with open(filepath) as config_file:
            if filepath.suffix == '.json':
                json_config.update(json.load(config_file))
            elif filepath.suffix == '.yaml':
                json_config.update(yaml.load(config_file, Loader=yaml.FullLoader))

    return json_config


def ask_for_token(json_config):
    print('There is no ~/.sclack file. Let\'s create one!')
    token = input('What is your Slack workspace token? ')  # pylint: disable = input-builtin
    json_config['workspaces'] = {'default': token}


def run():
    config = load_configuration()
    if config.get('logging', None):
        logging.config.dictConfig(config['logging'])
    App(config).start()


def async_connect_signal(widget, signal, callback, *args):
    @functools.wraps(callback)
    def signal_task(*args):
        loop.create_task(callback(*args))

    urwid.connect_signal(widget, signal, signal_task, *args)

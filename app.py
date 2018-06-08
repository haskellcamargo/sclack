#!/usr/bin/env python3
import asyncio
import concurrent.futures
import functools
import json
import os
import requests
import subprocess
import sys
import tempfile
import urwid
from datetime import datetime
from slackclient import SlackClient
from pyslack import config
from pyslack.components import Attachment, Channel, ChannelHeader, ChatBox, Dm
from pyslack.components import Indicators, MarkdownText
from pyslack.components import Message, MessageBox, Profile, ProfileSideBar
from pyslack.components import Reaction, SideBar, TextDivider
from pyslack.components import Time, User
from pyslack.image import Image
from pyslack.loading import LoadingChatBox, LoadingSideBar
from pyslack.store import Store

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h24'),
    ('profile', '', '', '', 'white', 'h233'),
    ('profile_icon', '', '', '', 'h244', 'h233'),
    ('attachment_title', '', '', '', 'bold,h33', 'h235'),
    ('chatbox', '', '', '', 'white', 'h235'),
    ('chatbox_header', '', '', '', 'h255', 'h235'),
    ('free_slack_limit', '', '', '', 'white', 'h238'),
    ('triangle_divider', '', '', '', 'h235', 'h238'),
    ('message_input', '', '', '', 'h255', 'h235'),
    ('prompt', '', '', '', 'white', 'h244'),
    ('prompt_arrow', '', '', '', 'h244', 'h235'),
    ('active_prompt', '', '', '', 'white', 'h27'),
    ('active_prompt_arrow', '', '', '', 'h27', 'h235'),
    ('datetime', '', '', '', 'h239', 'h235'),
    ('username', '', '', '', 'h71,underline', 'h235'),
    ('message', '', '', '', 'h253', 'h235'),
    ('history_date', '', '', '', 'h244', 'h235'),
    ('is_typing', '', '', '', 'h244', 'h235'),
    ('selected_channel', '', '', '', 'white', 'h162'),
    ('active_channel', '', '', '', 'white', 'h33'),
    ('active_message', '', '', '', 'white', 'h237'),
    ('active_link', '', '', '', 'h21,underline', 'h237'),
    ('separator', '', '', '', 'h244', 'h235'),
    ('edited', '', '', '', 'h239', 'h235'),
    ('starred', '', '', '', 'h214', 'h235'),
    ('reaction', '', '', '', 'h27', 'h235'),
    ('presence_active', '', '', '', 'h40', 'h24'),
    ('presence_away', '', '', '', 'h239', 'h24'),
    ('link', '', '', '', 'h21,underline', 'h235'),
    ('cite', '', '', '', 'italics,white', 'h235'),
    ('app_badge', '', '', '', 'h235', 'h248'),
    ('field_title', '', '', '', 'white,bold,underline', 'h235'),
    ('field_value', '', '', '', 'h253', 'h235'),
    ('italics', '', '', '', 'italics,white', 'h235'),
    ('bold', '', '', '', 'bold,h254', 'h235'),
    ('code', '', '', '', 'h124', 'h252'),
    ('loading_message', '', '', '', 'white', 'h235'),
    ('loading_active_block', '', '', '', 'h99', 'h235')
]

loop = asyncio.get_event_loop()

class App:
    message_box = None

    def __init__(self, service_path, slack_token):
        urwid.set_encoding('UTF-8')
        sidebar = LoadingSideBar()
        chatbox = LoadingChatBox('Everything is terrible!')
        self.columns = urwid.Columns([
            ('fixed', 25, urwid.AttrWrap(sidebar, 'sidebar')),
            urwid.AttrWrap(chatbox, 'chatbox')
        ])
        self.urwid_loop = urwid.MainLoop(
            urwid.Frame(urwid.AttrMap(self.columns, 'app')),
            palette=palette,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=self.unhandled_input
        )
        self.configure_screen(self.urwid_loop.screen)

    def start(self):
        self.store = Store(slack_token)
        self._loading = True
        loop.create_task(self.animate_loading())
        loop.create_task(self.component_did_mount())
        self.urwid_loop.run()

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
            loop.run_in_executor(executor, self.store.load_groups),
            loop.run_in_executor(executor, self.store.load_users)
        )
        profile = Profile(name=self.store.state.auth['user'])
        channels = [
            Channel(
                id=channel['id'],
                name=channel['name'],
                is_private=channel['is_private']
            )
            for channel in self.store.state.channels
        ]
        dms = []
        for dm in self.store.state.dms:
            user = self.store.find_user_by_id(dm['user'])
            if user:
                dms.append(Dm(name=user.get('real_name', user['name']), user=dm['user']))
        self.sidebar = SideBar(profile, channels, dms, title=self.store.state.auth['team'])
        urwid.connect_signal(self.sidebar, 'go_to_channel', self.go_to_channel)

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
        self.chatbox = ChatBox(messages, header, self.message_box)
        urwid.connect_signal(self.chatbox, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(self.chatbox, 'go_to_sidebar', self.go_to_sidebar)

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
                user.get('real_name', user['name']),
                user['profile'].get('status_text', None),
                user['profile'].get('tz_label', None),
                user['profile'].get('phone', None),
                user['profile'].get('email', None),
                user['profile'].get('skype', None)
            )
            loop.create_task(self.load_profile_avatar(user['profile'].get('image_512'), profile))
            self.columns.contents.append((profile, ('given', 35, False)))

    def render_chatbox_header(self):
        return ChannelHeader(
            name=self.store.state.channel['name'],
            topic=self.store.state.channel['topic']['value'],
            num_members=len(self.store.state.channel['members']),
            pin_count=self.store.state.pin_count,
            is_private=self.store.state.channel.get('is_group', False),
            is_starred=self.store.state.channel.get('is_starred', False)
        )

    def render_messages(self, messages):
        _messages = []
        previous_date = None
        today = datetime.today().date()
        for message in messages:
            message_date = datetime.fromtimestamp(float(message['ts'])).date()
            if not previous_date or previous_date != message_date:
                previous_date = message_date
                if message_date == today:
                    date_text = 'Today'
                else:
                    date_text = message_date.strftime('%A, %B %d')
                _messages.append(TextDivider(('history_date', date_text), 'center'))

            is_app = False
            if message.get('subtype') == 'bot_message':
                bot = (self.store.find_user_by_id(message['bot_id'])
                    or self.store.find_or_load_bot(message['bot_id']))
                if bot:
                    user_id = message['bot_id']
                    user_name = bot.get('profile', {}).get('display_name') or bot.get('name')
                    color = bot.get('color')
                    is_app = 'app_id' in bot
                else:
                    continue
            else:
                user = self.store.find_user_by_id(message['user'])
                user_id = user['id']
                user_name = user['profile']['display_name'] or user.get('name')
                color = user.get('color')

            time = Time(message['ts'])
            user = User(user_id, user_name, color, is_app)
            text = MarkdownText(message['text'])
            indicators = Indicators('edited' in message, message.get('is_starred', False))
            reactions = [
                Reaction(reaction['name'], reaction['count'])
                for reaction in message.get('reactions', [])
            ]
            file = message.get('file')
            attachments = []
            for attachment in message.get('attachments', []):
                attachment_widget = Attachment(
                    title=attachment.get('title'),
                    fields=attachment.get('fields'),
                    color=attachment.get('color'),
                    pretext=attachment.get('pretext'),
                    footer=attachment.get('footer')
                )
                image_url = attachment.get('image_url')
                if image_url:
                    loop.create_task(self.load_picture_async(
                        image_url,
                        attachment.get('image_width', 500),
                        attachment_widget,
                        auth=False
                    ))
                attachments.append(attachment_widget)
            message = Message(
                time,
                user,
                text,
                indicators,
                attachments=attachments,
                reactions=reactions
            )
            if file and file.get('filetype') in ('bmp', 'gif', 'jpeg', 'jpg', 'png'):
                loop.create_task(self.load_picture_async(
                    file['url_private'],
                    file.get('original_w', 500),
                    message
                ))
            urwid.connect_signal(message, 'go_to_profile', self.go_to_profile)
            _messages.append(message)
        return _messages

    @asyncio.coroutine
    def _go_to_channel(self, channel_id):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            yield from asyncio.gather(
                loop.run_in_executor(executor, self.store.load_channel, channel_id),
                loop.run_in_executor(executor, self.store.load_messages, channel_id)
            )
            messages = self.render_messages(self.store.state.messages)
            header = self.render_chatbox_header()
            self.chatbox.body.body[:] = messages
            self.chatbox.header = header
            self.chatbox.message_box.is_read_only = self.store.state.channel.get('is_read_only', False)
            self.sidebar.select_channel(channel_id)
            self.urwid_loop.set_alarm_in(0, lambda *args: self.chatbox.body.scroll_to_bottom())
            self.go_to_chatbox()

    def go_to_channel(self, channel_id):
        loop.create_task(self._go_to_channel(channel_id))

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

    def set_insert_mode(self):
        self.columns.focus_position = 1
        self.chatbox.focus_position = 'footer'
        self.message_box.focus_position = 1

    def go_to_chatbox(self):
        self.columns.focus_position = 1
        self.chatbox.focus_position = 'body'

    def go_to_sidebar(self):
        if len(self.columns.contents) > 2:
            self.columns.contents.pop()
        self.columns.focus_position = 0

    def unhandled_input(self, key):
        if key == 'c' and self.message_box:
            return self.go_to_chatbox()

        if key == 'i' and self.message_box:
            return self.set_insert_mode()

        elif key == 'esc':
            return self.go_to_sidebar()

        elif key == 'q':
            raise urwid.ExitMainLoop

    def configure_screen(self, screen):
        screen.set_terminal_properties(colors=256)
        screen.set_mouse_tracking()

if __name__ == '__main__':
    slack_token = config.get_pyslack_config().get('DEFAULT', 'Token')
    service_path = os.path.join(os.path.dirname(sys.argv[0]), 'service.py')
    app = App(service_path, slack_token)
    app.start()

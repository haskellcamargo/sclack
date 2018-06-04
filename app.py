#!/usr/bin/env python3
import asyncio
import concurrent.futures
import functools
import json
import os
import subprocess
import sys
import urwid
from datetime import datetime
from slackclient import SlackClient
from pyslack import config
from pyslack.components import Channel, ChannelHeader, ChatBox, Dm, Indicators
from pyslack.components import MarkdownText, Message, MessageBox, Profile
from pyslack.components import SideBar, TextDivider, Time, User
from pyslack.loading import LoadingChatBox, LoadingSideBar
from pyslack.store import Store

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h24'),
    ('chatbox', '', '', '', 'white', 'h235'),
    ('chatbox_header', '', '', '', 'h255', 'h235'),
    ('message_input', '', '', '', 'h255', 'h235'),
    ('prompt', '', '', '', 'white', 'h27'),
    ('prompt_arrow', '', '', '', 'h27', 'h235'),
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

    @asyncio.coroutine
    def mount_chatbox(self, executor, channel):
        yield from asyncio.gather(
            loop.run_in_executor(executor, self.store.load_channel, channel),
            loop.run_in_executor(executor, self.store.load_messages, channel)
        )
        messages = []
        previous_date = None
        today = datetime.today().date()
        for message in self.store.state.messages:
            message_date = datetime.fromtimestamp(float(message['ts'])).date()
            if not previous_date or previous_date != message_date:
                previous_date = message_date
                if message_date == today:
                    date_text = 'Today'
                else:
                    date_text = message_date.strftime('%A, %B %d')
                messages.append(TextDivider(date_text, 'center'))
            user = self.store.find_user_by_id(message['user'])
            time = Time(message['ts'])
            user = User(user['profile']['display_name'], user.get('color'))
            text = MarkdownText(message['text'])
            indicators = Indicators('edited' in message, message.get('is_starred', False))
            messages.append(Message(
                time,
                user,
                text,
                indicators
            ))
        header = ChannelHeader(
            name=self.store.state.channel['name'],
            topic=self.store.state.channel['topic']['value'],
            num_members=len(self.store.state.channel['members']),
            pin_count=self.store.state.pin_count,
            is_private=self.store.state.channel.get('is_group', False),
            is_starred=self.store.state.channel.get('is_starred', False)
        )
        self._loading = False
        self.chatbox = ChatBox(
            messages,
            header,
            message_box=MessageBox(
                user=self.store.state.auth['user']
            )
        )

    def unhandled_input(self, key):
        if key in ('q', 'esc'):
            raise urwid.ExitMainLoop

    def configure_screen(self, screen):
        screen.set_terminal_properties(colors=256)
        screen.set_mouse_tracking()

if __name__ == '__main__':
    slack_token = config.get_pyslack_config().get('DEFAULT', 'Token')
    service_path = os.path.join(os.path.dirname(sys.argv[0]), 'service.py')
    app = App(service_path, slack_token)
    app.start()

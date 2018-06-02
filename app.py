#!/usr/bin/env python3
import asyncio
import concurrent.futures
import functools
import json
import os
import subprocess
import sys
import urwid
from slackclient import SlackClient
from pyslack import config
from pyslack.components import Channel, Profile, SideBar
from pyslack.loading import LoadingChatBox, LoadingSideBar

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h24'),
    ('chatbox', '', '', '', 'h99', 'h235'),
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
    ('loading_active_block', '', '', '', 'white', 'h235')
]

loop = asyncio.get_event_loop()

class App:
    def __init__(self, service_path, slack_token):
        urwid.set_encoding('UTF-8')
        self.sidebar = LoadingSideBar()
        self.chatbox = LoadingChatBox('Everything is terrible!')
        self.columns = urwid.Columns([
            ('fixed', 25, urwid.AttrWrap(self.sidebar, 'sidebar')),
            urwid.AttrWrap(self.chatbox, 'chatbox')
        ])
        self.app = urwid.Frame(urwid.AttrMap(self.columns, 'app'))
        self.urwid_loop = urwid.MainLoop(
            self.app,
            palette=palette,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=self.unhandled_input
        )
        self.configure_screen(self.urwid_loop.screen)
        self.slack_token = slack_token

    def start(self):
        self.slack = SlackClient(self.slack_token)
        self._loading = True
        loop.create_task(self.animate_loading())
        loop.create_task(self.component_did_mount())
        self.urwid_loop.run()

    async def animate_loading(self):
        def update(*args):
            self.chatbox.circular_loading.next_frame()
            if self._loading:
                self.urwid_loop.set_alarm_in(0.2, update)
        update()

    async def component_did_mount(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(executor, self.slack.api_call, 'auth.test'),
                loop.run_in_executor(executor, functools.partial(
                    self.slack.api_call, 'conversations.list',
                    exclude_archived=True, types='public_channel,private_channel,im,mpim'
                ))
            ]
            [identity, conversations] = await asyncio.gather(*futures)
            # Filter only channels and create components
            channels = []
            for channel in conversations['channels']:
                if ('is_channel' in channel
                    and channel['is_member']
                    and (channel['is_channel'] or not channel['is_mpim'])):
                    channels.append(Channel(channel['name'], channel['is_private']))
            channels.sort()
            self.sidebar = SideBar(Profile(identity['user']), channels, identity['team'])
            self.columns.contents[0][0].original_widget = self.sidebar
            self._loading = False

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

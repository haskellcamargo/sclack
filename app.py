#!/usr/bin/env python3
import asyncio
import json
import os
import subprocess
import sys
import time
import urwid
from slackclient import SlackClient
from pyslack import config
from pyslack.components import Channel, Profile, SideBar
from pyslack.loading import LoadingChatBox, LoadingSideBar

PIPE_BUFFER_READ_SIZE = 0x1000

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
        self.chatbox = LoadingChatBox('Everything is terrible!', loop)
        self.columns = urwid.Columns([
            ('fixed', 25, urwid.AttrWrap(self.sidebar, 'sidebar')),
            urwid.AttrWrap(self.chatbox, 'chatbox')
        ])
        self.app = urwid.Frame(urwid.AttrMap(self.columns, 'app'))
        urwid_loop = urwid.MainLoop(
            self.app,
            palette=palette,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=self.unhandled_input
        )
        self.configure_screen(urwid_loop.screen)
        self.loop = urwid_loop
        self.start_server(service_path, slack_token)

    def handle_message(self, data):
        raw_data = data.decode('utf-8')

        # Handle buffer creation
        if len(raw_data) == PIPE_BUFFER_READ_SIZE:
            self._buffer = self._buffer + raw_data
            return

        # End of continuation, seek and reset
        if self._buffer:
            raw_data = self._buffer + raw_data
            self._buffer = ''

        message = json.loads(raw_data)
        if 'pyslack_type' in message:
            if message['pyslack_type'] == 'auth':
                self.sidebar = SideBar(
                    Profile(message['user']),
                    title=message['team']
                )
                self.chatbox.status_message = 'Loading yourself'
                self.columns.contents[0][0].original_widget = urwid.AttrWrap(self.sidebar, 'sidebar')
            if message['pyslack_type'] == 'channels':
                for channel in message['channels']:
                    channel = Channel(channel['name'], is_private=channel['is_private'])
                    self.sidebar.add_channel(channel)
                self.chatbox.status_message = 'Loading channels'

    def start_server(self, service_path, slack_token):
        stdout = self.loop.watch_pipe(self.handle_message)
        self._buffer = ''
        self.server = subprocess.Popen(
            ['python3', '-u', service_path, '--token', slack_token],
            stdout=stdout,
            close_fds=True
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
    app.loop.run()
    app.server.kill()

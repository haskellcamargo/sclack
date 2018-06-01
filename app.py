#!/usr/bin/env python3
import asyncio
import urwid
from slackclient import SlackClient
from pyslack import config
import time
import queue
import sys
import threading
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
    def __init__(self, message_queue):
        urwid.set_encoding('UTF-8')
        sidebar = urwid.AttrWrap(LoadingSideBar(), 'sidebar')
        chatbox = urwid.AttrWrap(LoadingChatBox(loop), 'chatbox')
        app = urwid.Frame(urwid.AttrWrap(urwid.Columns([
            ('fixed', 25, sidebar),
            chatbox
        ]), 'app'))
        urwid_loop = urwid.MainLoop(
            app,
            palette=palette,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=self.unhandled_input
        )
        self.configure_screen(urwid_loop.screen)
        self.message_queue = message_queue
        self.loop = urwid_loop
        self.component_did_mount(self.loop)

    def component_did_mount(self, loop, *args):
        loop.set_alarm_in(0.5, self.component_did_mount)
        try:
            message = self.message_queue.get_nowait()
            print(message)
        except queue.Empty:
            return

    def unhandled_input(self, key):
        if key in ('q', 'esc'):
            raise urwid.ExitMainLoop

    def configure_screen(self, screen):
        screen.set_terminal_properties(colors=256)
        screen.set_mouse_tracking()

def load_initial_data(stop_event, message_queue):
    while not stop_event.wait(timeout=1.0):
        message_queue.put(time.strftime('time %X'))

if __name__ == '__main__':
    stop_event = threading.Event()
    message_queue = queue.Queue()
    threading.Thread(target=load_initial_data, args=[stop_event, message_queue], name='load_initial_data').start()
    App(message_queue).loop.run()
    stop_event.set()
    for thread in threading.enumerate():
        if thread != threading.current_thread():
            thread.join()

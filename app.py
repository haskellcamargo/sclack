#!/usr/bin/env python3
import asyncio
import urwid
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

class App(urwid.Frame):
    def __init__(self):
        sidebar = urwid.AttrWrap(LoadingSideBar(), 'sidebar')
        chatbox = urwid.AttrWrap(LoadingChatBox(loop), 'chatbox')
        app = urwid.AttrWrap(urwid.Columns([
            ('fixed', 25, sidebar),
            chatbox
        ]), 'app')
        super(App, self).__init__(app)

def unhandled_input(key):
    if key in ('q', 'esc'):
        raise urwid.ExitMainLoop

def configure_screen(screen):
    screen.set_terminal_properties(colors=256)
    screen.set_mouse_tracking()

if __name__ == '__main__':
    urwid.set_encoding('UTF-8')
    app = App()
    urwid_loop = urwid.MainLoop(
        app,
        palette=palette,
        event_loop=urwid.AsyncioEventLoop(loop=loop),
        unhandled_input=unhandled_input
    )
    configure_screen(urwid_loop.screen)
    urwid_loop.run()

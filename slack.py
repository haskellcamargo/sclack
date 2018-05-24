#!/usr/bin/env python3
import urwid
from slackclient import SlackClient
from pyslack import config
import pprint

token = config.get_pyslack_config().get('DEFAULT', 'Token')
slack = SlackClient(token)

def exit_on_q(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h99')
]

class Sidebar(urwid.BoxWidget):
    def __init__(self):
        team = slack.api_call('team.info')['team']
        channels = slack.api_call('channels.list', exclude_members=True, exclude_archived=True)['channels']
        channels = list(filter(lambda channel: channel['is_member'], channels))
        self.contents = urwid.SimpleListWalker([
            urwid.Text(' # ' + channel['name']) for channel in channels
        ])
        self.listbox = urwid.LineBox(urwid.ListBox(self.contents), title=team['domain'], title_align='left')
        self.edit = False

    def render(self, size, focus=False):
        return self.listbox.render(size, focus)

    def keypress(self, size, key):
        self.listbox.keypress(size, key)

def main():
    sidebar = urwid.AttrWrap(Sidebar(), 'sidebar')
    columns = urwid.Columns([
        ('fixed', 25, sidebar)
    ], 1)
    app = urwid.Frame(urwid.AttrWrap(columns, 'app'))
    loop = urwid.MainLoop(app, palette, unhandled_input=exit_on_q)
    loop.screen.set_terminal_properties(colors=256)
    loop.run()

main()

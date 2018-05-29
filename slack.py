#!/usr/bin/env python3
import urwid
from slackclient import SlackClient
from pyslack import config
from pyslack.components import TextDivider, SideBar
import pprint

token = config.get_pyslack_config().get('DEFAULT', 'Token')
#slack = SlackClient(token)

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h98'),
    ('chatbox', '', '', '', 'h99', 'h235'),
    ('chatbox_header', '', '', '', 'h255', 'h235'),
    ('message_input', '', '', '', 'h255', 'h235'),
    ('prompt', '', '', '', 'h85', 'h235'),
    ('datetime', '', '', '', 'h239', 'h235'),
    ('username', '', '', '', 'h71,underline', 'h235'),
    ('message', '', '', '', 'h253', 'h235'),
    ('history_date', '', '', '', 'h244', 'h235'),
    ('is_typing', '', '', '', 'h244', 'h235'),
    ('reveal focus', '', '', '', 'h99', 'h77')
]

def main():
    urwid.set_encoding('UTF-8')
    sidebar = urwid.AttrWrap(SideBar(), 'sidebar')
    ## FRAME
    header = urwid.AttrWrap(urwid.Pile([
        urwid.Columns([
            ('fixed', 1, urwid.Divider(u'─')),
            ('fixed', 11, urwid.Text('#compiler', align='center')),
            urwid.Divider(u'─')
        ]),
        urwid.Text(u' 👨 11 | Everything is terrible'),
        urwid.Columns([
            urwid.Divider(u'─'),
            ('fixed', 14, urwid.Text(('history_date', 'Satuday 25th'), align='center')),
            urwid.Divider(u'─')
        ])
    ]), 'chatbox_header')

    is_typing_text = 'vitorebatista is typing...'
    is_typing = urwid.Columns([
        ('fixed', 1, urwid.Divider(u'─')),
        ('fixed', len(is_typing_text) + 2, urwid.Text(('is_typing', is_typing_text), align='center')),
        urwid.Divider(u'─'),
    ])

    footer = urwid.AttrWrap(urwid.Pile([
        is_typing,
        urwid.Edit(('prompt', ' haskellcamargo> '), multiline=True),
        urwid.Divider(u'─')
    ]), 'message_input')


    messages = [
        urwid.Text([
            ('datetime', ' [22:10] '),
            ('username', 'takanuva'),
            ('message', ' sou javeiro ' + str(i))
        ]) for i in range(1, 100)
    ]

    body = urwid.ListBox(urwid.SimpleListWalker(messages))
    frame = urwid.Frame(body, header=header, footer=footer)
    ##
    chatbox = urwid.AttrWrap(frame, 'chatbox')
    columns = urwid.Columns([
        ('fixed', 25, sidebar),
        ('weight', 1, chatbox)
    ])
    app = urwid.Frame(urwid.AttrWrap(columns, 'app'))
    loop = urwid.MainLoop(app, palette)
    loop.screen.set_terminal_properties(colors=256)
    loop.screen.set_mouse_tracking()
    loop.run()

main()

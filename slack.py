#!/usr/bin/env python3
import urwid
from slackclient import SlackClient
from pyslack import config
from pyslack.components import TextDivider, SideBar, Channel
import pprint

token = config.get_pyslack_config().get('DEFAULT', 'Token')

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
    ('reveal focus', '', '', '', 'h99', 'h77'),
    ('active_channel', '', '', '', 'white', 'h142')
]

def main():
    slack = SlackClient(token)
    slack_channels = slack.api_call('conversations.list', exclude_archived=True, types='public_channel,private_channel,im,mpim')['channels']

    my_channels = list(filter(lambda channel:
        'is_channel' in channel and channel['is_member'] and (channel['is_channel'] or not channel['is_mpim']),
        slack_channels))
    my_channels.sort(key=lambda channel: channel['name'])

    channels = [
        Channel(channel['name'], is_private=channel['is_private'])
        for channel in my_channels
    ]

    urwid.set_encoding('UTF-8')
    sidebar = urwid.AttrWrap(SideBar(channels=channels, title='nginformatica'), 'sidebar')
    ## FRAME
    header = urwid.AttrWrap(urwid.Pile([
        TextDivider('#compiler'),
        urwid.Text(u' 👨 11 | Everything is terrible'),
        TextDivider(('history_date', 'Satuday 25th'), align='center')
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

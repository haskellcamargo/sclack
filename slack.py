#!/usr/bin/env python3
import urwid
from slackclient import SlackClient
from pyslack import config
from pyslack.components import TextDivider, SideBar, Channel, MessageBox, ChannelHeader, ChatBox, Message, Profile
from datetime import datetime
import pprint


token = config.get_pyslack_config().get('DEFAULT', 'Token')

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
    ('active_channel', '', '', '', 'white', 'h162'),
    ('separator', '', '', '', 'h244', 'h235'),
    ('edited', '', '', '', 'h239', 'h235'),
    ('presence_active', '', '', '', 'h40', 'h24'),
    ('presence_away', '', '', '', 'h239', 'h24')
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

    profile = Profile(name="haskellcamargo", is_online=False)
    sidebar = urwid.AttrWrap(SideBar(channels=channels, title='nginformatica', profile=profile), 'sidebar')
    header = urwid.AttrWrap(ChannelHeader(
        date='Today',
        topic='Tudo é terrível',
        num_members=13,
        name='rung',
        is_private=False
    ), 'chatbox_header')
    message_box = urwid.AttrWrap(MessageBox(user='haskellcamargo', typing='vitorebatista'), 'message_input')

    messages = slack.api_call('channels.history', unreads=True, channel='C1A1MMJAE')['messages']
    messages.reverse()
    # pprint.pprint(messages)
    # return
    messages = [
        Message(
            time=datetime.fromtimestamp(float(message['ts'])).strftime('%H:%M'),
            user='...',
            edited=('edited' in message)
        ) for message in messages
    ]
    chatbox = urwid.AttrWrap(ChatBox(
        messages=messages,
        header=header,
        message_box=message_box
    ), 'chatbox')
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

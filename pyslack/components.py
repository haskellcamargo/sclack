import urwid

options = {
    'icons': {
        'channel': '\uF198',
        'divider': '\uE0B1',
        'full_divider': '\uE0C6',
        'full_star': '\uF005',
        'keyboard': '\uF11C',
        'line_star': '\uF006',
        'offline': '\uF10C',
        'online': '\uF111',
        'person': '\uF415',
        'private_channel': '\uF023'
    }
}

class BreadCrumbs(urwid.Text):
    def intersperse(self, iterable, delimiter):
        it = iter(iterable)
        yield next(it)
        for elem in it:
            yield delimiter
            yield elem

    def __init__(self, elements=[]):
        separator = ('separator', ' {} '.format(options['icons']['divider']))
        body = list(self.intersperse(elements, separator))
        super(BreadCrumbs, self).__init__([' '] + body)

class Channel(urwid.AttrMap):
    def __init__(self, name, is_private=False):
        body = urwid.SelectableIcon(' {} {}'.format(
            options['icons']['private_channel' if is_private else 'channel'],
            name
        ))
        super(Channel, self).__init__(body, None, 'active_channel')

class ChannelHeader(urwid.Pile):
    def __init__(self, date, topic, num_members, name, is_private=False, starred=False):
        star_icon = options['icons']['full_star' if starred else 'line_star']
        body = [
            TextDivider(' {} {}'.format(
                options['icons']['private_channel' if is_private else 'channel'],
                name
            )),
            BreadCrumbs([
                star_icon,
                '{} {}'.format(options['icons']['person'], num_members),
                topic
            ]),
            TextDivider(('history_date', date), align='center')
        ]
        super(ChannelHeader, self).__init__(body)

class ChatBox(urwid.Frame):
    def __init__(self, messages, header, message_box):
        body = urwid.ListBox(urwid.SimpleFocusListWalker(messages))
        super(ChatBox, self).__init__(body, header=header, footer=message_box)

class Message(urwid.Columns):
    def __init__(self, time, user_id, user_name, text, is_starred=False, is_edited=False, reactions=[]):
        time_column = ('fixed', 8, urwid.Text(('datetime', ' {} │'.format(time))))
        starred_column = []
        edited_column = []
        
        # Starred message
        if is_starred:
            starred_column = [('fixed', 3, urwid.Text(('starred', ' {} '.format(options['icons']['full_star']))))]
        
        # Edited message
        if is_edited:
            edited_column = [('fixed', 10, urwid.Text(('edited', ' (edited) ')))]

        content = urwid.Text(('message', text))
        if reactions:
            content = urwid.Pile([
                content,
                urwid.Columns(reactions, dividechars=1)
            ])

        super(Message, self).__init__([
            time_column,
            ('pack', urwid.Text([
                ('background_{}'.format(user_id), ' {} '.format(user_name)),
                ('foreground_{}'.format(user_id), options['icons']['full_divider']),
                ' '
            ])),
            content
        ] + starred_column + edited_column)

class MessageBox(urwid.Pile):
    def __init__(self, user, typing=None):
        if typing != None:
            top_separator = TextDivider(('is_typing', '{} {} is typing...'.format(
                options['icons']['keyboard'],
                typing
            )))
        else:
            top_separator = urwid.Divider('─')
        prompt = urwid.Edit(('prompt', [
            ' ', user, ' ', ('prompt_arrow', options['icons']['full_divider'] + ' ')
        ]))
        body = [
            top_separator,
            prompt,
            urwid.Divider('─')
        ]
        super(MessageBox, self).__init__(body)

class Profile(urwid.Text):
    def __init__(self, name, is_online=True):
        if is_online:
            presence_icon = ('presence_active', ' {} '.format(options['icons']['online']))
        else:
            presence_icon = ('presence_away', ' {} '.format(options['icons']['offline']))
        body = [presence_icon, name]
        super(Profile, self).__init__(body)

class Reaction(urwid.Text):
    def __init__(self, name, count=0):
        text = '[:{}: {}]'.format(name, count)
        super(Reaction, self).__init__(('reaction', text))

class SideBar(urwid.Frame):
    def __init__(self, profile, channels=[], title=''):
        header = TextDivider(title)
        footer = urwid.Divider('─')
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker([
            profile,
            TextDivider('Channels')
        ] + channels))
        super(SideBar, self).__init__(self.listbox, header=header, footer=footer)

class TextDivider(urwid.Columns):
    def __init__(self, text='', align='left', char='─'):
        text_size = len(text if isinstance(text, str) else text[1]) + 2
        text_widget = ('fixed', text_size, urwid.Text(text, align='center'))
        if align == 'right':
            body = [
                urwid.Divider(char),
                text_widget,
                ('fixed', 1, urwid.Divider(char))
            ]
        elif align == 'center':
            body = [
                urwid.Divider(char),
                text_widget,
                urwid.Divider(char)
            ]
        else:
            body = [
                ('fixed', 1, urwid.Divider(char)),
                text_widget,
                urwid.Divider(char)
            ]
        super(TextDivider, self).__init__(body)

import urwid
import pprint
from datetime import datetime
from .markdown import MarkdownText

options = {
    'icons': {
        'block': '\u258C',
        'block_bottom': '\u2598',
        'block_top': '\u2596',
        'channel': '\uF198',
        'divider': '\uE0B1',
        'edit': '\uF040',
        'full_divider': '\uE0C6',
        'full_star': '\uF005',
        'heart': '\uF004',
        'keyboard': '\uF11C',
        'line_star': '\uF006',
        'offline': '\uF10C',
        'online': '\uF111',
        'person': '\uF415',
        'pin': '\uF435',
        'private_channel': '\uF023',
        'square': '\uF445'
    }
}

class Attachment(urwid.Pile):
    def __init__(self, color='#CCC', title=None, title_link=None, pretext=None, fields=None, footer=None):
        body = []
        if pretext:
            body.append(urwid.Text(MarkdownText(pretext).markup))
        if fields:
            body.append(Box(Fields(fields), color=color))
        super(Attachment, self).__init__(body)

class Box(urwid.AttrWrap):
    def __init__(self, widget, color):
        body = urwid.LineBox(widget,
            lline=options['icons']['block'],
            tlcorner=options['icons']['block_top'],
            blcorner=options['icons']['block_bottom'],
            tline='', trcorner='', rline='', bline='', brcorner='.')
        super(Box, self).__init__(body, urwid.AttrSpec(color, 'h235'))

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
    def __init__(self, id, name, is_private=False, is_selected=False):
        self.id = id
        self.name = name
        self.is_private = is_private
        body = urwid.SelectableIcon(' {} {}'.format(
            options['icons']['private_channel' if is_private else 'channel'],
            name
        ))
        attr_map = None
        if is_selected:
            attr_map = 'selected_channel'
        super(Channel, self).__init__(body, attr_map, 'active_channel')

    def select(self):
        self.is_selected = True
        self.attr_map = {None: 'selected_channel'}

class ChannelHeader(urwid.Pile):
    def __init__(self, name, topic, date=None, num_members=0, is_private=False,
        pin_count=0, is_starred=False):
        if is_starred:
            star_icon = ('starred', options['icons']['full_star'])
        else:
            star_icon = options['icons']['line_star']

        # Fixed date divider
        if date:
            date_divider = TextDivider(('history_date', date), align='center')
        else:
            date_divider = urwid.Divider('─')

        body = [
            TextDivider(' {} {}'.format(
                options['icons']['private_channel' if is_private else 'channel'],
                name
            )),
            BreadCrumbs([
                star_icon,
                '{} {}'.format(options['icons']['person'], num_members),
                '{} {}'.format(options['icons']['pin'], pin_count),
                topic
            ]),
            date_divider
        ]
        super(ChannelHeader, self).__init__(body)

class ChatBox(urwid.Frame):
    def __init__(self, messages, header, message_box):
        self.body = ChatBoxMessages(messages=messages)
        self.body.scroll_to_bottom()
        super(ChatBox, self).__init__(self.body, header=header, footer=message_box)

class ChatBoxMessages(urwid.ListBox):
    __metaclass__ = urwid.MetaSignals
    signals = ['set_auto_scroll']

    def __init__(self, messages=[]):
        self.body = urwid.SimpleFocusListWalker(messages)
        super(ChatBoxMessages, self).__init__(self.body)
        self.auto_scroll = True

    @property
    def auto_scroll(self):
        return self._auto_scroll

    @auto_scroll.setter
    def auto_scroll(self, switch):
        if type(switch) != bool:
            return
        self._auto_scroll = switch
        urwid.emit_signal(self, 'set_auto_scroll', switch)

    def keypress(self, size, key):
        super(ChatBoxMessages, self).keypress(size, key)
        if key in ('page up', 'page down'):
            self.auto_scroll = self.get_focus()[1] == len(self.body) - 1

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press' and button in (4, 5):
            if button == 4:
                self.keypress(size, 'up')
                return True
            else:
                self.keypress(size, 'down')
                return True
        else:
            return super(ChatBoxMessages, self).mouse_event(size, event, button, col, row, focus)

    def scroll_to_bottom(self):
        if self.auto_scroll and len(self.body):
            self.set_focus(len(self.body) - 1)

class Dm(urwid.AttrMap):
    def __init__(self, name, user):
        if len(name) > 21:
            name = name[:18] + '...'
        if user == 'USLACKBOT':
            icon = ('presence_active', options['icons']['heart'])
        else:
            icon = ('presence_away', options['icons']['offline'])
        body = urwid.SelectableIcon([' ', icon, ' ', name])
        super(Dm, self).__init__(body, None, 'active_channel')

class Fields(urwid.Pile):
    def chunks(self, list, size):
        for i in range(0, len(list), size):
            yield list[i:i + size]

    def render_field(self, field):
        text = []
        title = field.get('title', '')
        if title != '':
            text.append(('field_title', title))
            text.append('\n')
        text.append(('field_value', MarkdownText(field['value']).markup))
        return urwid.Text(text)

    def __init__(self, fields=[], columns=2, width=30):
        pile = []
        for chunk in self.chunks(fields, columns):
            pile.append(urwid.Columns([
                ('fixed', width, self.render_field(field))
                for field in chunk
            ]))
        super(Fields, self).__init__(pile)

class Indicators(urwid.Columns):
    def __init__(self, is_edited=False, is_starred=False):
        indicators = []
        self.size = 0
        if is_edited:
            edited_text = urwid.Text(('edited', ' {} '.format(options['icons']['edit'])))
            indicators.append(edited_text)
            self.size = self.size + 3
        if is_starred:
            starred_text = urwid.Text(('starred', ' {} '.format(options['icons']['full_star'])))
            indicators.append(starred_text)
            self.size = self.size + 3
        super(Indicators, self).__init__(indicators)

class Message(urwid.AttrMap):
    def __init__(self, time, user, text, indicators, file=None, reactions=[], attachments=[]):
        main_column = [urwid.Columns([('pack', user), text])]
        main_column.extend(attachments)

        if file:
            main_column.append(file)

        main_column.extend(reactions)
        main_column = urwid.Pile(main_column)
        columns = [
            ('fixed', 8, time),
            main_column,
            ('fixed', indicators.size, indicators)
        ]
        self.contents = urwid.Columns(columns)
        super(Message, self).__init__(self.contents, None, 'active_message')

    def selectable(self):
        return True

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
    def __init__(self, name, is_online=False):
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
    def __init__(self, profile, channels=[], dms=[], title=''):
        header = TextDivider(title)
        footer = urwid.Divider('─')
        stack = [
            profile,
            TextDivider('Channels')
        ]
        stack.extend(channels)
        stack.append(TextDivider('Direct Messages'))
        stack.extend(dms)
        self.walker = urwid.SimpleFocusListWalker(stack)
        self.listbox = urwid.ListBox(self.walker)
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

class Time(urwid.Text):
    def __init__(self, timestamp):
        time = datetime.fromtimestamp(float(timestamp)).strftime('%H:%M')
        super(Time, self).__init__(('datetime', ' {} │'.format(time)))

class User(urwid.Text):
    def __init__(self, name, color='333333', is_app=False):
        color='#{}'.format(self.shorten_hex(color))
        markup = [
            (urwid.AttrSpec('white', color), ' {} '.format(name)),
            (urwid.AttrSpec(color, 'h235'), options['icons']['full_divider']),
            ' '
        ]
        if is_app:
            markup.append(('app_badge', '[APP]'))
        super(User, self).__init__(markup)

    def shorten_hex(self, color):
        return '{}{}{}'.format(
            hex(round(int(color[:2], 16) / 17))[-1],
            hex(round(int(color[2:4], 16) / 17))[-1],
            hex(round(int(color[4:], 16) / 17))[-1]
        )
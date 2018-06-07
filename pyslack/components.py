import urwid
import pprint
import pyperclip
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
        'email': '\uF42F',
        'full_divider': '\uE0C6',
        'full_star': '\uF005',
        'heart': '\uF004',
        'keyboard': '\uF11C',
        'line_star': '\uF006',
        'offline': '\uF10C',
        'online': '\uF111',
        'person': '\uF415',
        'phone': '\uF095',
        'pin': '\uF435',
        'private_channel': '\uF023',
        'skype': '\uF17E',
        'square': '\uF445',
        'status': '\uF075',
        'timezone': '\uF0AC',
        'triangle_left': '\uE0BA',
        'triangle_right': '\uE0B8'
    }
}

class Attachment(urwid.Pile):
    def __init__(self, color=None, title=None, title_link=None, pretext=None, fields=None, footer=None):
        body = []
        if not color:
            color = 'CCCCCC'
        color = '#{}'.format(shorten_hex(color))
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

    def deselect(self):
        self.is_selected = False
        self.attr_map = {None: None}

class ChannelHeader(urwid.Pile):
    def on_set_date(self, divider):
        if not divider:
            self.contents.pop()
            self.contents.append((urwid.Divider('─'), ('pack', 1)))
        elif isinstance(self.contents[-1], tuple) and self.contents[-1][0] != divider:
            self.contents.pop()
            self.contents.append((divider, ('pack', 1)))

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
    __metaclass__ = urwid.MetaSignals
    signals = ['set_insert_mode', 'go_to_sidebar']

    def __init__(self, messages, header, message_box):
        self._header = header
        self.message_box = message_box
        self.body = ChatBoxMessages(messages=messages)
        self.body.scroll_to_bottom()
        urwid.connect_signal(self.body, 'set_date', self._header.on_set_date)
        super(ChatBox, self).__init__(self.body, header=header, footer=self.message_box)

    def keypress(self, size, key):
        if key == 'i':
            urwid.emit_signal(self, 'set_insert_mode')
            return True
        elif key == 'esc':
            urwid.emit_signal(self, 'go_to_sidebar')
            return True
        return super(ChatBox, self).keypress(size, key)

    @property
    def header(self):
        return self._header

    @header.setter
    def header(self, header):
        urwid.disconnect_signal(self.body, 'set_date', self._header.on_set_date)
        self._header = header
        urwid.connect_signal(self.body, 'set_date', self._header.on_set_date)
        self.set_header(self._header)

class ChatBoxMessages(urwid.ListBox):
    __metaclass__ = urwid.MetaSignals
    signals = ['set_auto_scroll', 'set_date']

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
        self.handle_floating_date(size)
        super(ChatBoxMessages, self).keypress(size, key)
        if key in ('page up', 'page down'):
            self.auto_scroll = self.get_focus()[1] == len(self.body) - 1

    def mouse_event(self, size, event, button, col, row, focus):
        self.handle_floating_date(size)
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

    def render(self, size, *args, **kwargs):
        self.handle_floating_date(size)
        return super(ChatBoxMessages, self).render(size, *args, **kwargs)

    def handle_floating_date(self, size):
        # No messages, no date
        if not self.focus:
            urwid.emit_signal(self, 'set_date', None)
            return
        (row_offset, _, focus_position, _, _), _, _ = self.calculate_visible(size, self.focus)
        index = abs(row_offset - focus_position)
        all_before = self.body[:index]
        all_before.reverse()
        text_divider = None
        for row in all_before:
            if isinstance(row, TextDivider):
                text_divider = row
                break
        urwid.emit_signal(self, 'set_date', text_divider)

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
    __metaclass__ = urwid.MetaSignals
    signals = ['go_to_profile']

    def __init__(self, time, user, text, indicators, reactions=[], attachments=[]):
        self.user_id = user.id
        self.original_text = text.original_text
        main_column = [urwid.Columns([('pack', user), text])]
        main_column.extend(attachments)
        self._file_index = len(main_column)
        if reactions:
            main_column.append(urwid.Columns([
                ('pack', reaction) for reaction in reactions
            ]))
        self.main_column = urwid.Pile(main_column)
        columns = [
            ('fixed', 8, time),
            self.main_column,
            ('fixed', indicators.size, indicators)
        ]
        self.contents = urwid.Columns(columns)
        super(Message, self).__init__(self.contents, None, 'active_message')

    def keypress(self, size, key):
        if key == 'y':
            pyperclip.copy(self.original_text)
            return True
        elif key == 'p':
            urwid.emit_signal(self, 'go_to_profile', self.user_id)
            return True
        return super(Message, self).keypress(size, key)

    def selectable(self):
        return True

    @property
    def file(self):
        return None

    @file.setter
    def file(self, file):
        self.main_column.contents.insert(self._file_index, (file, ('pack', 1)))

class MessageBox(urwid.AttrMap):
    def __init__(self, user, typing=None, is_read_only=False):
        self.read_only_widget = urwid.Text('You have no power here!', align='center')
        if typing != None:
            top_separator = TextDivider(('is_typing', '{} {} is typing...'.format(
                options['icons']['keyboard'],
                typing
            )))
        else:
            top_separator = urwid.Divider('─')
        self.prompt_widget = urwid.Edit(('prompt', [
            ' ', user, ' ', ('prompt_arrow', options['icons']['full_divider'] + ' ')
        ]))
        middle = urwid.WidgetPlaceholder(self.read_only_widget if is_read_only else self.prompt_widget)
        self.body = urwid.Pile([
            top_separator,
            middle,
            urwid.Divider('─')
        ])
        super(MessageBox, self).__init__(self.body, None, {
            'prompt': 'active_prompt',
            'prompt_arrow': 'active_prompt_arrow'
        })

    @property
    def is_read_only(self):
        return None

    @is_read_only.setter
    def is_read_only(self, read_only):
        if read_only:
            self.body.contents[1][0].original_widget = self.read_only_widget
        else:
            self.body.contents[1][0].original_widget = self.prompt_widget

    @property
    def focus_position(self):
        return self.body.focus_position

    @focus_position.setter
    def focus_position(self, focus_position):
        self.body.focus_position = focus_position

class Profile(urwid.Text):
    def __init__(self, name, is_online=False):
        if is_online:
            presence_icon = ('presence_active', ' {} '.format(options['icons']['online']))
        else:
            presence_icon = ('presence_away', ' {} '.format(options['icons']['offline']))
        body = [presence_icon, name]
        super(Profile, self).__init__(body)

class ProfileSideBar(urwid.AttrWrap):
    def format_row(self, icon, text):
        return urwid.Text([
            ' ',
            ('profile_icon', options['icons'][icon]),
            ' ',
            text
        ])

    def __init__(self, name, status=None, timezone=None, phone=None, email=None, skype=None):
        line = urwid.Divider('─')
        header = urwid.Pile([
            line,
            urwid.Text([' ', name]),
            line
        ])
        contents = []
        if status:
            contents.append(self.format_row('status', status))
        if timezone:
            contents.append(self.format_row('timezone', timezone))
        if phone:
            contents.append(self.format_row('phone', phone))
        if email:
            contents.append(self.format_row('email', email))
        if skype:
            contents.append(self.format_row('skype', skype))
        self.pile = urwid.Pile(contents)
        body = urwid.Frame(urwid.Filler(self.pile, valign='top'), header, line)
        super(ProfileSideBar, self).__init__(body, 'profile')

    @property
    def avatar(self):
        return self.pile.contents[0]

    @avatar.setter
    def avatar(self, avatar):
        self.pile.contents.insert(0, (avatar, ('pack', 1)))

class Reaction(urwid.Text):
    def __init__(self, name, count=0):
        text = '[:{}: {}]'.format(name, count)
        super(Reaction, self).__init__(('reaction', text))

class SideBar(urwid.Frame):
    __metaclass__ = urwid.MetaSignals
    signals = ['go_to_channel']

    def __init__(self, profile, channels=[], dms=[], title=''):
        self.channels = channels
        header = TextDivider(title)
        footer = urwid.Divider('─')
        stack = [
            profile,
            TextDivider('Channels')
        ]
        stack.extend(self.channels)
        stack.append(TextDivider('Direct Messages'))
        stack.extend(dms)
        self.walker = urwid.SimpleFocusListWalker(stack)
        self.listbox = urwid.ListBox(self.walker)
        super(SideBar, self).__init__(self.listbox, header=header, footer=footer)

    def select_channel(self, channel_id):
        for channel in self.channels:
            if channel.id == channel_id:
                channel.select()
            else:
                channel.deselect()

    def keypress(self, size, key):
        if key == 'enter':
            channel = self.listbox.focus
            urwid.emit_signal(self, 'go_to_channel', channel.id)
            return True

        return super(SideBar, self).keypress(size, key)

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press' and button in (4, 5):
            if button == 4:
                self.keypress(size, 'up')
                return True
            else:
                self.keypress(size, 'down')
                return True
        return super(SideBar, self).mouse_event(size, event, button, col, row, focus)

class TextDivider(urwid.Columns):
    def __init__(self, text='', align='left', char='─'):
        self.text = text
        text_size = len(text if isinstance(text, str) else text[1]) + 2
        self.text_widget = ('fixed', text_size, urwid.Text(text, align='center'))
        if align == 'right':
            body = [
                urwid.Divider(char),
                self.text_widget,
                ('fixed', 1, urwid.Divider(char))
            ]
        elif align == 'center':
            body = [
                urwid.Divider(char),
                self.text_widget,
                urwid.Divider(char)
            ]
        else:
            body = [
                ('fixed', 1, urwid.Divider(char)),
                self.text_widget,
                urwid.Divider(char)
            ]
        super(TextDivider, self).__init__(body)

class Time(urwid.Text):
    def __init__(self, timestamp):
        time = datetime.fromtimestamp(float(timestamp)).strftime('%H:%M')
        super(Time, self).__init__(('datetime', ' {} │'.format(time)))

class TriangleDivider(urwid.Text):
    def __init__(self):
        return super(TriangleDivider, self).__init__('')

    def render(self, size, focus=False):
        (maxcol,) = size
        _, attr = self.get_text()
        text = []
        for index in range(0, maxcol):
            triangle = 'triangle_left' if index % 2 == 0 else 'triangle_right'
            text.append(('triangle_divider', options['icons'][triangle]))
        self.set_text(text)
        return super(TriangleDivider, self).render(size, focus)

def shorten_hex(color):
    return '{}{}{}'.format(
        hex(round(int(color[:2], 16) / 17))[-1],
        hex(round(int(color[2:4], 16) / 17))[-1],
        hex(round(int(color[4:], 16) / 17))[-1]
    )

class User(urwid.Text):
    def __init__(self, id, name, color=None, is_app=False):
        self.id = id
        if not color:
            color = '333333'
        color='#{}'.format(shorten_hex(color))
        markup = [
            (urwid.AttrSpec('white', color), ' {} '.format(name)),
            (urwid.AttrSpec(color, 'h235'), options['icons']['full_divider']),
            ' '
        ]
        if is_app:
            markup.append(('app_badge', '[APP]'))
        super(User, self).__init__(markup)

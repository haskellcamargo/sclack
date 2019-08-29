import time
import re

import urwid
import pyperclip
import webbrowser
import urwid_readline
from datetime import datetime

from .emoji import emoji_codemap
from .markdown import MarkdownText
from .store import Store
from sclack.utils.channel import is_group, is_channel, is_dm
from sclack.utils.message import format_date_time


MARK_READ_ALARM_PERIOD = 3


def get_icon(name):
    return Store.instance.config['icons'][name]


class Box(urwid.AttrWrap):
    def __init__(self, widget, color):
        body = urwid.LineBox(widget,
            lline=get_icon('block'),
            tlcorner=get_icon('block_top'),
            blcorner=get_icon('block_bottom'),
            tline='', trcorner='', rline='', bline='', brcorner='')
        super(Box, self).__init__(body, urwid.AttrSpec(color, 'h235'))


class Attachment(Box):
    def __init__(self,
                 color=None,
                 service_name=None,
                 title=None,
                 title_link=None,
                 from_url=None,
                 author_name=None,
                 pretext=None,
                 text=None,
                 fields=None,
                 attachment_text=None,
                 ts=None,
                 footer=None):
        body = []
        if not color:
            color = 'CCCCCC'
        color = '#{}'.format(shorten_hex(color))

        self._image_index = 0
        self.from_url = from_url

        if service_name:
            body.append(urwid.Text(('attachment_title', service_name)))
            self._image_index = self._image_index + 1

        if title:
            body.append(urwid.Text(('attachment_title', title.strip())))
            self._image_index = self._image_index + 1

        if author_name:
            body.append(urwid.Text(('attachment_title', author_name)))
            self._image_index = self._image_index + 1

        if pretext:
            body.append(urwid.Text(MarkdownText(pretext).markup))
            self._image_index = self._image_index + 1

        text_display = attachment_text if attachment_text is not None else text
        if text_display:
            body.append(urwid.Text(MarkdownText(text_display.strip()).markup))

        if fields:
            body.append(Fields(fields))

        if footer or ts:
            footer_parts = []
            if footer:
                footer_parts.append(footer)
            if ts:
                footer_parts.append(format_date_time(ts))

            footer_text = ' | '.join(footer_parts)
            body.append(urwid.Text(MarkdownText(footer_text).markup))

        self.pile = urwid.Pile(body)

        super(Attachment, self).__init__(self.pile, color)

    @property
    def file(self):
        return None

    @file.setter
    def file(self, image):
        self.pile.contents.insert(self._image_index, (image, ('pack', 1)))


class BreadCrumbs(urwid.Text):
    def __init__(self, elements=()):
        separator = ('separator', ' {} '.format(get_icon('divider')))
        body = []
        for element in elements:
            body.append(element)
            body.append(separator)
        super(BreadCrumbs, self).__init__([' '] + body)


class Channel(urwid.AttrMap):
    __metaclass__ = urwid.MetaSignals
    signals = ['go_to_channel']

    def __init__(self, id, name, is_private=False, is_selected=False):
        self.id = id
        self.name = name
        self.is_private = is_private
        attr_map = 'inactive'
        if is_selected:
            attr_map = 'selected_channel'
        self.last_time_clicked = None
        self.unread = 0
        self.is_selected = is_selected
        self.body = urwid.SelectableIcon(self.get_markup(0))

        super(Channel, self).__init__(self.body, attr_map, 'active_channel')

    def get_markup(self, unread_count_display):
        counter_message = ''
        if unread_count_display != 0:
            counter_message = ' ({})'.format(unread_count_display)

        return ' {} {}{}'.format(
            get_icon('private_channel' if self.is_private else 'channel'),
            self.name,
            counter_message
        )

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press':
            now = time.time()
            if self.last_time_clicked and (now - self.last_time_clicked < 0.5):
                urwid.emit_signal(self, 'go_to_channel', self.id)
            self.last_time_clicked = now

    def set_unread(self, count):
        self.unread = count
        if not self.is_selected:
            if count > 0:
                self.attr_map = {None: 'unread_channel'}
            else:
                self.attr_map = {None: 'inactive'}

        self.body.set_text(self.get_markup(count))

    def select(self):
        self.is_selected = True
        self.attr_map = {None: 'selected_channel'}
        self.focus_map = {None: 'selected_channel'}
        self.set_unread(self.unread)

    def deselect(self):
        self.is_selected = False
        self.attr_map = {None: 'inactive'}
        self.focus_map = {None: 'active_channel'}
        self.set_unread(self.unread)


class ChannelHeader(urwid.Pile):
    def on_set_date(self, divider):
        if not divider:
            self.contents.pop()
            self.contents.append((urwid.Divider('─'), ('pack', 1)))
        elif isinstance(self.contents[-1], tuple) and self.contents[-1][0] != divider:
            self.contents.pop()
            self.contents.append((divider, ('pack', 1)))

    def __init__(self, name, topic, date=None, num_members=0, more_members=False, 
        is_private=False, pin_count=0, is_starred=False, 
        is_dm_workaround_please_remove_me=False):
        if is_starred:
            star_icon = ('starred', get_icon('full_star'))
        else:
            star_icon = get_icon('line_star')

        # Fixed date divider
        if date:
            date_divider = TextDivider(('history_date', date), align='center')
        else:
            date_divider = urwid.Divider('─')

        self.original_topic = topic
        if is_dm_workaround_please_remove_me:
            self.topic_widget = urwid.Text(topic)
        else:
            self.topic_widget = ChannelTopic(topic)
        body = urwid.Columns([
            ('pack', BreadCrumbs([
                star_icon,
                '{} {}{}'.format(get_icon('person'), num_members, 
                    "+" if more_members else ""),
                '{} {}'.format(get_icon('pin'), pin_count)
            ])),
            urwid.AttrMap(self.topic_widget, None, 'edit_topic_focus')
        ])
        icon = TextDivider(' {} {}'.format(
            get_icon('private_channel' if is_private else 'channel'),
            name
        ))
        contents = []
        if not is_dm_workaround_please_remove_me:
            contents.append(icon)
        contents.extend([
            body,
            date_divider
        ])
        self.is_dm_workaround_please_remove_me = is_dm_workaround_please_remove_me
        super(ChannelHeader, self).__init__(contents)

    def restore_topic(self):
        if not self.is_dm_workaround_please_remove_me:
            self.topic_widget.set_edit_text(self.original_topic)

    def go_to_end_of_topic(self):
        self.topic_widget.set_edit_pos(len(self.original_topic))


class ChannelTopic(urwid.Edit):
    __metaclass__ = urwid.MetaSignals
    signals = ['done']

    def __init__(self, topic):
        caption = '{} '.format(get_icon('edit'))
        super(ChannelTopic, self).__init__(caption, edit_text=topic)

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return True
        return super(ChannelTopic, self).keypress(size, key)


class ChatBox(urwid.Frame):
    __metaclass__ = urwid.MetaSignals
    signals = ['go_to_sidebar', 'open_quick_switcher', 'set_insert_mode', 'mark_read', 'open_set_snooze']

    def __init__(self, messages, header, message_box, event_loop):
        self._header = header
        self.message_box = message_box
        self.body = ChatBoxMessages(messages=messages, event_loop=event_loop)
        self.body.scroll_to_bottom()
        urwid.connect_signal(self.body, 'set_date', self._header.on_set_date)
        urwid.connect_signal(self.body, 'set_insert_mode', self.set_insert_mode)
        urwid.connect_signal(self.body, 'mark_read', self.mark_as_read)
        super(ChatBox, self).__init__(self.body, header=header, footer=self.message_box)

    def set_insert_mode(self):
        urwid.emit_signal(self, 'set_insert_mode')

    def mark_as_read(self, data):
        urwid.emit_signal(self, 'mark_read', data)

    def keypress(self, size, key):
        keymap = Store.instance.config['keymap']
        if key == keymap['open_quick_switcher']:
            urwid.emit_signal(self, 'open_quick_switcher')
            return True
        if key == keymap['set_snooze']:
            urwid.emit_signal(self, 'open_set_snooze')
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
    signals = ['set_auto_scroll', 'set_date', 'set_insert_mode', 'mark_read']

    def __init__(self, messages=(), event_loop=None):
        self.body = urwid.SimpleFocusListWalker(messages)
        super(ChatBoxMessages, self).__init__(self.body)
        self.auto_scroll = True
        self.last_keypress = (0, None, 0)
        self.event_loop = event_loop

    @property
    def auto_scroll(self):
        return self._auto_scroll

    @auto_scroll.setter
    def auto_scroll(self, switch):
        if type(switch) != bool:
            return

        self._auto_scroll = switch
        urwid.emit_signal(self, 'set_auto_scroll', switch)

    def mark_read_emit(self, loop, data):
        urwid.emit_signal(self, 'mark_read', data)

    def keypress(self, size, key):
        keymap = Store.instance.config['keymap']
        self.handle_floating_date(size)

        if key in (keymap['cursor_up'], keymap['cursor_down'], 'up', 'down', ):
            now = time.time()
            max_focus = self.get_focus()[1]

            if now - self.last_keypress[0] < MARK_READ_ALARM_PERIOD and self.last_keypress[1] is not None:
                if max_focus < self.last_keypress[2]:
                    max_focus = self.last_keypress[2]

                self.event_loop.remove_alarm(self.last_keypress[1])

            self.last_keypress = (
                now,
                self.event_loop.set_alarm_in(MARK_READ_ALARM_PERIOD, self.mark_read_emit, max_focus),
                max_focus
            )

        # Go to insert mode
        if key == 'down' and self.get_focus()[1] == len(self.body) - 1:
            urwid.emit_signal(self, 'set_insert_mode')
            return True

        super(ChatBoxMessages, self).keypress(size, key)

        if key in ('page up', 'page down'):
            self.auto_scroll = self.get_focus()[1] == len(self.body) - 1

        if key == keymap['cursor_up']:
            self.keypress(size, 'up')
        if key == keymap['cursor_down']:
            self.keypress(size, 'down')

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

    def scroll_to_new_messages(self):
        for index, widget in enumerate(self.body):
            if isinstance(widget, NewMessagesDivider):
                return self.set_focus(index)

        return self.scroll_to_bottom()

    def scroll_to_bottom(self):
        if self.auto_scroll and len(self.body):
            self.set_focus(len(self.body) - 1)

    def go_to_last_message(self):
        if len(self.body) > 0:
            self.set_focus(len(self.body) - 1)

    def render(self, size, *args, **kwargs):
        self.handle_floating_date(size)
        return super(ChatBoxMessages, self).render(size, *args, **kwargs)

    def handle_floating_date(self, size):
        # No messages, no date
        if not self.focus:
            urwid.emit_signal(self, 'set_date', None)
            return
        middle, top, _ = self.calculate_visible(size, self.focus)
        row_offset, widget, focus_position, _, _ = middle
        index = focus_position - row_offset + top[0]
        all_before = self.body[:index]
        all_before.reverse()
        text_divider = None
        for row in all_before:
            if isinstance(row, TextDivider):
                text_divider = row
                break
        urwid.emit_signal(self, 'set_date', text_divider)


class Dm(urwid.AttrMap):
    def __init__(self, id, name, user, you=False, unread=0, is_selected=False):
        self.id = id
        self.user = user
        self.name = name
        self.you = you
        self.presence = 'away'
        self.unread = unread
        self.body = urwid.SelectableIcon(self.get_markup())
        self.is_selected = is_selected

        attr_map = 'inactive'
        if is_selected:
            attr_map = 'selected_channel'

        super(Dm, self).__init__(self.body, attr_map, 'active_channel')

    def get_markup(self, presence='away'):
        if self.user == 'USLACKBOT':
            icon = ('presence_active', get_icon('heart'))
        elif presence == 'active':
            icon = ('presence_active', get_icon('online'))
        else:
            icon = ('presence_away', get_icon('offline'))

        sidebar_width = Store.instance.config['sidebar']['width']
        name = self.name

        if self.you:
            name = self.name + ' (you)'

        message_unread = ''
        if not self.you and self.unread > 0:
            message_unread = ' ({})'.format(self.unread)
        padding_length = 4 + len(message_unread)

        if len(name) > sidebar_width - padding_length:
            padding_length += 3  # 3 for ...
            name = '{}{}{}'.format(
                name[:(sidebar_width - padding_length)],
                message_unread,
                '...'
            )
        else:
            name = '{}{}'.format(
                name,
                message_unread,
            )

        return [' ', icon, ' ', name]

    def set_unread(self, count):
        self.unread = count
        if not self.is_selected:
            if count > 0:
                self.attr_map = {None: 'unread_channel'}
            else:
                self.attr_map = {None: 'inactive'}

        self.body.set_text(self.get_markup(self.presence))

    def set_presence(self, presence):
        self.presence = presence
        self.original_widget.set_text(self.get_markup(presence))
        if presence == 'active':
            self.attr_map = {None: 'unread_channel'}
        else:
            self.attr_map = {None: 'inactive'}

    def select(self):
        self.is_selected = True
        self.attr_map = {
            None: 'selected_channel',
            'presence_away': 'selected_channel'
        }
        self.set_presence(self.presence)
        self.attr_map = {None: 'selected_channel'}
        self.focus_map = {None: 'selected_channel'}

    def deselect(self):
        self.is_selected = False
        self.attr_map = {None: None}
        self.set_presence(self.presence)


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
            edited_text = urwid.Text(('edited', ' {} '.format(get_icon('edit'))))
            indicators.append(edited_text)
            self.size = self.size + 3
        if is_starred:
            starred_text = urwid.Text(('starred', ' {} '.format(get_icon('full_star'))))
            indicators.append(starred_text)
            self.size = self.size + 3
        super(Indicators, self).__init__(indicators)


class MessageBox(urwid.AttrMap):
    def __init__(self, user, typing=None, is_read_only=False):
        self.read_only_widget = urwid.Text('You have no power here!', align='center')
        if typing != None:
            top_separator = TextDivider(('is_typing', '{} {} is typing...'.format(
                get_icon('keyboard'),
                typing
            )))
        else:
            top_separator = urwid.Divider('─')
        self.prompt_widget = MessagePrompt(user)
        middle = urwid.WidgetPlaceholder(self.read_only_widget if is_read_only else self.prompt_widget)
        self.body = urwid.Pile([
            urwid.WidgetPlaceholder(top_separator),
            middle,
            urwid.Divider('─')
        ])
        self._typing = typing
        super(MessageBox, self).__init__(self.body, None, {'prompt': 'active_prompt'})

    @property
    def typing(self):
        return self._typing

    @typing.setter
    def typing(self, typing=None):
        if typing is None:
            self.body.contents[0][0].original_widget = urwid.Divider('─')
        else:
            self.body.contents[0][0].original_widget = TextDivider(
                ('is_typing', '{} {} is typing...'.format(get_icon('keyboard'), typing))
            )

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

    @property
    def text(self):
        return None

    @text.setter
    def text(self, text):
        self.prompt_widget.set_edit_text(text)
        self.prompt_widget.set_edit_pos(len(text))


class MessagePrompt(urwid_readline.ReadlineEdit):
    __metaclass__ = urwid.MetaSignals
    signals = ['submit_message', 'go_to_last_message']

    def __init__(self, user):
        super(MessagePrompt, self).__init__([('prompt', ' {}'.format(user)), ' '])

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'submit_message', self.get_edit_text())
            return True
        elif key == 'up':
            urwid.emit_signal(self, 'go_to_last_message')
            return True
        return super(MessagePrompt, self).keypress(size, key)


class Profile(urwid.Text):
    def __init__(self, name, is_online=False, is_snoozed=False):
        self.name = name
        self.is_online = is_online
        self.is_snoozed = is_snoozed
        super(Profile, self).__init__(self.body)

    @property
    def body(self):
        if self.is_snoozed:
            presence_icon = ('presence_active', ' {} '.format(get_icon('snooze')))
        elif self.is_online:
            presence_icon = ('presence_active', ' {} '.format(get_icon('online')))
        else:
            presence_icon = ('presence_away', ' {} '.format(get_icon('offline')))

        snooze_str = ' (snoozed) ' if self.is_snoozed else ''

        return [presence_icon, self.name, snooze_str]

    def set_snooze(self, is_snoozed):
        self.is_snoozed = is_snoozed
        self.set_text(self.body)


class ProfileSideBar(urwid.AttrWrap):
    def format_row(self, icon, text):
        return urwid.Text([
            ' ',
            ('profile_icon', get_icon(icon)),
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
        name = emoji_codemap.get(name, name)
        text = '[{} {}]'.format(name, count)
        super(Reaction, self).__init__(('reaction', text))


class SideBar(urwid.Frame):
    __metaclass__ = urwid.MetaSignals
    signals = ['go_to_channel']

    def __init__(self, profile, channels=(), dms=(), stars=(), title=''):
        self.profile = profile
        self.channels = channels
        self.stars = stars
        self.dms = dms
        self.groups = ()
        self.last_time_clicked = None

        # Subscribe to receive message from channels to select them
        for channel in self.channels:
            urwid.connect_signal(channel, 'go_to_channel', self.go_to_channel)
        header = TextDivider(title)
        footer = urwid.Divider('─')
        stack = [
            profile,
            TextDivider('Starred')
        ]
        stack.extend(stars)
        stack.append(TextDivider('Channels'))
        stack.extend(self.channels)
        stack.append(TextDivider('Direct Messages'))
        stack.extend(dms)

        self.walker = urwid.SimpleFocusListWalker(stack)
        self.listbox = urwid.ListBox(self.walker)
        super(SideBar, self).__init__(self.listbox, header=header, footer=footer)

    def get_all_channels(self):
        """
        List Channels including Starred items
        :return:
        """
        channels_starred = list(filter(
            lambda starred: is_channel(starred.id),
            self.stars
        ))
        channels_starred.extend(self.channels)

        return channels_starred

    def get_all_dms(self):
        """
        List DM including Starred items
        :return:
        """
        dms = list(filter(
            lambda starred: is_dm(starred.id),
            self.stars
        ))
        dms.extend(self.dms)

        return dms

    def get_all_groups(self):
        """
        List Groups including Starred items
        :return:
        """
        groups = list(filter(
            lambda starred: is_group(starred.id),
            self.stars
        ))
        groups.extend(self.groups)

        return groups

    def get_targets_by_id(self, channel_id):
        """
        For different channel_id we get different data from: Groups, DMs, Channels
        :param channel_id:
        :return:
        """
        targets = None
        if is_channel(channel_id):
            targets = self.get_all_channels()
        elif is_dm(channel_id):
            targets = self.get_all_dms()
        elif is_group(channel_id):
            targets = self.get_all_groups()
        return targets

    def select_channel(self, channel_id):
        """
        :param channel_id:
        :return:
        """
        for channel in self.get_all_channels():
            if channel.id == channel_id:
                channel.select()
            else:
                channel.deselect()

        for dm in self.get_all_dms():
            if dm.id == channel_id:
                dm.select()
            else:
                dm.deselect()

    def update_items(self, event):
        """
        Update unread count for side bar items
        :param event:
        :return:
        """
        channel_id = event.get('channel')
        target = self.get_targets_by_id(channel_id)

        chat_detail = Store.instance.get_channel_info(event.get('channel'))
        new_count = chat_detail.get('unread_count_display', 0)

        for widget in target:
            if widget.id == channel_id:
                widget.set_unread(new_count)

    def go_to_channel(self, channel):
        urwid.emit_signal(self, 'go_to_channel', channel)

    def keypress(self, size, key):
        keymap = Store.instance.config['keymap']
        if key == 'enter':
            channel = self.listbox.focus
            self.go_to_channel(channel.id)
            return True
        if key == keymap['cursor_up']:
            self.keypress(size, 'up')
            return True
        if key == keymap['cursor_down']:
            self.keypress(size, 'down')
            return True

        return super(SideBar, self).keypress(size, key)

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press':
            if button in (4, 5):
                if button == 4:
                    self.keypress(size, 'up')
                    return True
                else:
                    self.keypress(size, 'down')
                    return True
            else:
                now = time.time()
                if self.last_time_clicked and (now - self.last_time_clicked < 0.5):
                    self.keypress(size, 'enter')
                self.last_time_clicked = now

        return super(SideBar, self).mouse_event(size, event, button, col, row, focus)


class NewMessagesDivider(urwid.AttrWrap):
    def __init__(self, text='', date=None, char='─'):
        text_size = len(text if isinstance(text, str) else text[1]) + 2
        self.text_widget = ('fixed', text_size, urwid.Text(('new_messages_text', text), align='center'))
        body = [
            urwid.Divider(char)
        ]
        if date is None:
            body.append(self.text_widget)
            body.append(('fixed', 1, urwid.Divider(char)))
        else:
            date_size = len(date if isinstance(date, str) else date[1]) + 2
            date_widget = ('fixed', date_size, urwid.Text(date, align='center'))
            body.append(date_widget)
            body.append(urwid.Divider(char))
            body.append(self.text_widget)
            body.append(('fixed', 1, urwid.Divider(char)))
        super(NewMessagesDivider, self).__init__(urwid.Columns(body), 'new_messages_line')


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

def shorten_hex(color):
    if color.startswith('#'):
        color = color[1:]

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
        color = '#{}'.format(shorten_hex(color))
        markup = [
            (urwid.AttrSpec(color, 'h235'), '{} '.format(name))
        ]
        if is_app:
            markup.append(('app_badge', '[APP]'))
        super(User, self).__init__(markup)


class ThreadText(urwid.Text):
    """
    A text element used to indicate the number of messages in a thread
    """
    def __init__(self, num_replies):
        color = "#" + shorten_hex('146BF7')
        markup = [
            (urwid.AttrSpec(color, 'h235'), 'Thread ({})'.format(num_replies))
        ]
        super(ThreadText, self).__init__(markup)


class Workspace(urwid.AttrMap):
    __metaclass__ = urwid.MetaSignals
    signals = ['select_workspace']

    def __init__(self, number, name):
        separator = ('inactive', format(get_icon('divider')))
        self.number = number
        self.text = ' {}: {} '.format(number, name)
        self.body = urwid.SelectableIcon([self.text, separator])
        self.last_time_clicked = None
        super(Workspace, self).__init__(self.body, 'inactive', None)

    def select(self):
        self.attr_map = {None: 'selected_workspace'}
        self.body.set_text([
            self.text,
            ('selected_workspace_separator', format(get_icon('full_divider')))
        ])

    def deselect(self):
        self.attr_map = {None: None}
        self.body.set_text([
            self.text,
            ('inactive', format(get_icon('divider')))
        ])

    def select_as_previous(self):
        self.attr_map = {None: None}
        self.body.set_text([
            self.text,
            ('previous_workspace_separator', format(get_icon('full_divider')))
        ])

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press':
            now = time.time()
            if self.last_time_clicked and (now - self.last_time_clicked < 0.5):
                urwid.emit_signal(self, 'select_workspace', self.number)
            self.last_time_clicked = now


class Workspaces(urwid.AttrWrap):
    __metaclass__ = urwid.MetaSignals
    signals = ['switch_workspace']

    def __init__(self, workspaces):
        body = []
        for index, (name, _) in enumerate(workspaces):
            workspace = Workspace(index + 1, name)
            urwid.connect_signal(workspace, 'select_workspace', self.switch_workspace)
            body.append(('pack', workspace))
        self.selected = 0
        self.body = body
        self.body[0][1].select()
        super(Workspaces, self).__init__(urwid.Columns(body), 'workspace_line')

    def select(self, number):
        for workspace in self.body:
            workspace[1].deselect()

        if number > 1:
            self.body[number - 2][1].select_as_previous()

        self.body[number - 1][1].select()
        new_selected = number - 1

        self.selected = new_selected

    def switch_workspace(self, number):
        if number - 1 != self.selected:
            self.select(number)
            urwid.emit_signal(self, 'switch_workspace', number)

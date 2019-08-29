import re

import urwid
import pyperclip
import webbrowser
from sclack.store import Store
from sclack.components import ThreadText
from sclack.component.time import Time


class Message(urwid.AttrMap):
    __metaclass__ = urwid.MetaSignals
    signals = [
        'delete_message',
        'edit_message',
        'get_permalink',
        'go_to_profile',
        'go_to_sidebar',
        'quit_application',
        'set_insert_mode',
        'mark_read',
    ]

    def __init__(self, ts, channel_id, user, text, indicators, reactions=(), attachments=(), responses=()):
        self.ts = ts
        self.channel_id = channel_id
        self.user_id = user.id
        self.markdown_text = text
        self.original_text = text.original_text
        self.text_widget = urwid.WidgetPlaceholder(text)
        main_column = [urwid.Columns([('pack', user), self.text_widget])]
        main_column.extend(attachments)
        self._file_index = len(main_column)

        if reactions:
            main_column.append(urwid.Columns([
                ('pack', reaction) for reaction in reactions
            ]))

        if responses:
            main_column.append(ThreadText(len(responses)))

        self.main_column = urwid.Pile(main_column)
        columns = [
            ('fixed', 7, Time(ts)),
            self.main_column,
            ('fixed', indicators.size, indicators)
        ]
        self.contents = urwid.Columns(columns)
        super(Message, self).__init__(self.contents, None, {
            None: 'active_message',
            'message': 'active_message'
        })

    def keypress(self, size, key):
        keymap = Store.instance.config['keymap']

        if key == keymap['delete_message']:
            urwid.emit_signal(self, 'delete_message', self, self.user_id, self.ts)
            return True
        elif key == keymap['edit_message']:
            urwid.emit_signal(self, 'edit_message', self, self.user_id, self.ts, self.original_text)
            return True
        elif key == keymap['go_to_profile']:
            urwid.emit_signal(self, 'go_to_profile', self.user_id)
            return True
        elif key == keymap['go_to_sidebar'] or key == keymap['cursor_left']:
            urwid.emit_signal(self, 'go_to_sidebar')
            return True
        elif key == keymap['quit_application']:
            urwid.emit_signal(self, 'quit_application')
            return True
        elif key == keymap['set_insert_mode']:
            urwid.emit_signal(self, 'set_insert_mode')
            return True
        elif key == keymap['yank_message']:
            try:
                pyperclip.copy(self.original_text)
            except pyperclip.PyperclipException:
                pass
            return True
        elif key == keymap['get_permalink']:
            # FIXME
            urwid.emit_signal(self, 'get_permalink', self, self.channel_id, self.ts)
        elif key == 'enter':
            browser_name = Store.instance.config['features']['browser']

            for item in self.markdown_text.markup:
                type, value = item

                if type == 'link' and re.compile(r'^https?://').search(value):
                    browser_instance = webbrowser if browser_name == '' else webbrowser.get(browser_name)
                    browser_instance.open(value, new=2)
                    break

        return super(Message, self).keypress(size, key)

    def set_text(self, text):
        self.text_widget.original_widget = text

    def set_edit_mode(self):
        self.set_attr_map({
            None: 'editing_message',
            'message': 'editing_message'
        })

    def unset_edit_mode(self):
        self.set_attr_map({
            None: None,
            'message': None
        })

    def selectable(self):
        return True

    @property
    def file(self):
        return None

    @file.setter
    def file(self, file):
        self.main_column.contents.insert(self._file_index, (file, ('pack', 1)))

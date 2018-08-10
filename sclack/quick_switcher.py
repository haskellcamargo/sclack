import urwid
import time
import unicodedata
from .store import Store

def get_icon(name):
    return Store.instance.config['icons'][name]

def remove_diacritic(input):
    '''
    Accept a unicode string, and return a normal string (bytes in Python 3)
    without any diacritical marks.
    '''
    return unicodedata.normalize('NFKD', input).encode('ASCII', 'ignore').decode()

class QuickSwitcherItem(urwid.AttrMap):
    def __init__(self, icon, title, id):
        markup = [' ', icon, ' ', title]
        self.id = id
        super(QuickSwitcherItem, self).__init__(
            urwid.SelectableIcon(markup),
            None,
            {
                None: 'active_quick_switcher_item',
                'quick_search_presence_active': 'quick_search_active_focus',
                'quick_search_presence_away': 'active_quick_switcher_item'
            }
        )

class QuickSwitcherList(urwid.ListBox):
    def __init__(self, items):
        self.body = urwid.SimpleFocusListWalker(items)
        super(QuickSwitcherList, self).__init__(self.body)

class QuickSwitcher(urwid.AttrWrap):
    __metaclass__ = urwid.MetaSignals
    signals = ['close_quick_switcher', 'go_to_channel']

    def __init__(self, base, event_loop):
        priority = []
        lines = []
        self.event_loop = event_loop
        for channel in Store.instance.state.channels:
            if channel.get('is_channel', False):
                lines.append({
                    'icon': get_icon('private_channel'),
                    'title': channel['name'], 'type': 'channel',
                    'id': channel['id']
                })
            elif channel.get('is_group', False):
                lines.append({
                    'id': channel['id'], 'icon': get_icon('channel'),
                    'title': channel['name'], 'type': 'channel'
                })
        for dm in Store.instance.state.dms:
            user = Store.instance.find_user_by_id(dm['user'])
            if user:
                name = user.get('display_name') or user.get('real_name') or user['name']
                online = user['id'] in Store.instance.state.online_users
                if user['id'] == 'USLACKBOT':
                    icon = ('quick_search_presence_active', get_icon('heart'))
                    priority.append({'id': dm['id'], 'icon': icon, 'title': name, 'type': 'user'})
                elif online:
                    icon = ('quick_search_presence_active', get_icon('online'))
                    priority.append({'id': dm['id'], 'icon': icon, 'title': name, 'type': 'user'})
                else:
                    icon = ('quick_search_presence_away', get_icon('offline'))
                    lines.append({'id': dm['id'],'icon': icon, 'title': name, 'type': 'user'})
        priority.sort(key=lambda item: item['title'])
        lines.sort(key=lambda item: item['title'])
        self.header = urwid.Edit('')
        self.original_items = priority + lines
        widgets = [QuickSwitcherItem(item['icon'], item['title'], item['id']) for item in self.original_items]
        self.quick_switcher_list = QuickSwitcherList(widgets)
        switcher = urwid.LineBox(
            urwid.Frame(self.quick_switcher_list, header=self.header),
            title='Jump to...',
            title_align='left'
        )
        overlay = urwid.Overlay(
            switcher,
            base,
            align = 'center',
            width = ('relative', 40),
            valign = 'middle',
            height = 15
        )
        self.last_keypress = (time.time() - 0.3, None)
        super(QuickSwitcher, self).__init__(overlay, 'quick_switcher_dialog')

    @property
    def filtered_items(self):
        return self.original_items

    @filtered_items.setter
    def filtered_items(self, items):
        self.quick_switcher_list.body[:] = [
            QuickSwitcherItem(item['icon'], item['title'], item['id'])
            for item in items
        ]

    def set_filter(self, loop, data):
        text = self.header.get_edit_text()
        if len(text) > 0:
            text = remove_diacritic(text)
            if text[0] == '@':
                self.filtered_items = [
                    item for item in self.original_items
                    if (item['type'] == 'user' and (text[1:].lower() in remove_diacritic(item['title'].lower()) or text[1:].strip() == ''))
                ]
            elif text[0] == '#':
                self.filtered_items = [
                    item for item in self.original_items
                    if (item['type'] == 'channel' and (text[1:].lower() in remove_diacritic(item['title'].lower()) or text[1:].strip() == ''))
                ]
            else:
                self.filtered_items = [
                    item for item in self.original_items
                    if text.lower() in remove_diacritic(item['title'].lower())
                ]
        else:
            self.filtered_items = self.original_items

    def keypress(self, size, key):
        reserved_keys = ('up', 'down', 'esc', 'page up', 'page down')
        if key in reserved_keys:
            return super(QuickSwitcher, self).keypress(size, key)
        elif key == 'enter':
            focus = self.quick_switcher_list.body.get_focus()
            if focus[0]:
                urwid.emit_signal(self, 'go_to_channel', focus[0].id)
                return True
        self.header.keypress((size[0],), key)
        now = time.time()
        if now - self.last_keypress[0] < 0.3 and self.last_keypress[1] is not None:
            self.event_loop.remove_alarm(self.last_keypress[1])
        self.last_keypress = (now, self.event_loop.set_alarm_in(0.3, self.set_filter))


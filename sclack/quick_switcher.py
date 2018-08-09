import urwid
from .store import Store

class QuickSwitcherItem(urwid.AttrMap):
    def __init__(self, icon, title):
        markup = [' ', icon, ' ', title]
        super(QuickSwitcherItem, self).__init__(urwid.SelectableIcon(markup), None, {
            None: 'active_quick_switcher_item'
        })

class QuickSwitcherList(urwid.ListBox):
    def __init__(self, items):
        self.widgets = [QuickSwitcherItem(item['icon'], item['title']) for item in items]
        self.body = urwid.SimpleFocusListWalker(self.widgets)
        super(QuickSwitcherList, self).__init__(self.body)

class QuickSwitcher(urwid.AttrWrap):
    __metaclass__ = urwid.MetaSignals
    signals = ['close_quick_switcher']

    def __init__(self, base):
        items = QuickSwitcherList([
            {'icon': '#', 'title': 'random'},
            {'icon': '#', 'title': 'general'}
        ])
        self.header = urwid.Edit('')
        switcher = urwid.LineBox(
            urwid.Frame(items, header=self.header),
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
        return super(QuickSwitcher, self).__init__(overlay, 'quick_switcher_dialog')

    def keypress(self, size, key):
        if len(key) == 1 and key.isalnum():
            self.header.insert_text(key)
        elif key == 'backspace':
            self.header.set_edit_text(self.header.get_edit_text()[:-1])
        return super(QuickSwitcher, self).keypress(size, key)

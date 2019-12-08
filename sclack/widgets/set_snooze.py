import urwid

from sclack.components import get_icon


class SetSnoozeWidgetItem(urwid.AttrMap):
    def __init__(self, icon, title, id):
        markup = [' ', icon, ' ', title]
        self.id = id
        super(SetSnoozeWidgetItem, self).__init__(
            urwid.SelectableIcon(markup),
            None,
            {
                None: 'active_set_snooze_item',
                'quick_search_presence_active': 'quick_search_active_focus',
            },
        )


class SetSnoozeWidgetList(urwid.ListBox):
    def __init__(self, items):
        self.body = urwid.SimpleFocusListWalker(items)
        super(SetSnoozeWidgetList, self).__init__(self.body)


class SetSnoozeWidget(urwid.AttrWrap):
    signals = ['close_set_snooze', 'set_snooze_time']

    def __init__(self, base, event_loop):
        lines = []
        self.event_loop = event_loop

        snooze_times = [
            {'label': 'Off', 'time': 0,},
            {'label': '20 minutes', 'time': 20,},
            {'label': '1 hour', 'time': 60,},
            {'label': '2 hours', 'time': 120,},
            {'label': '4 hours', 'time': 240,},
            {'label': '8 hours', 'time': 480,},
            {'label': '24 hours', 'time': 1400,},
        ]

        for snooze_time in snooze_times:
            lines.append(
                {
                    'icon': get_icon('alarm_snooze'),
                    'title': snooze_time['label'],
                    'time': snooze_time['time'],
                }
            )

        self.header = urwid.Edit('')

        self.original_items = lines
        widgets = [
            SetSnoozeWidgetItem(item['icon'], item['title'], item['time'])
            for item in self.original_items
        ]

        self.snooze_time_list = SetSnoozeWidgetList(widgets)

        snooze_list = urwid.LineBox(
            urwid.Frame(self.snooze_time_list, header=self.header),
            title='Snooze notifications',
            title_align='left',
        )
        overlay = urwid.Overlay(
            snooze_list,
            base,
            align='center',
            width=('relative', 15),
            valign='middle',
            height=10,
            right=5,
        )
        super(SetSnoozeWidget, self).__init__(overlay, 'set_snooze_dialog')

    def keypress(self, size, key):
        reserved_keys = ('up', 'down', 'page up', 'page down')
        if key in reserved_keys:
            return super(SetSnoozeWidget, self).keypress(size, key)
        elif key == 'enter':
            focus = self.snooze_time_list.body.get_focus()
            if focus[0]:
                urwid.emit_signal(self, 'set_snooze_time', focus[0].id)
                urwid.emit_signal(self, 'close_set_snooze')
                return True
        elif key == 'esc':
            focus = self.snooze_time_list.body.get_focus()
            if focus[0]:
                urwid.emit_signal(self, 'close_set_snooze')
                return True

        self.header.keypress((size[0],), key)

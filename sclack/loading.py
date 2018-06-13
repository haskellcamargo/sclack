import urwid
from .components import TextDivider, get_icon

def placeholder(size=10, left=0):
    return ((' ' * left)[:left] +
        (get_icon('square') * size)[:size])

class CircularLoading(urwid.Pile):
    _matrix = [
        ['\uE0BA', '\uE0B8'],
        ['\uE0BE', '\uE0BC']
    ]

    def __init__(self):
        self._index = 0
        self._shape = [
            urwid.Text([char for char in row], align='center')
            for row in self._matrix
        ]
        super(CircularLoading, self).__init__(self._shape)

    def next_frame(self):
        if self._index == 0:
            self._index = 1
        elif self._index == 1:
            self._index = 3
        elif self._index == 3:
            self._index = 2
        elif self._index == 2:
            self._index = 0

        active_row = int(self._index >= 2)
        old_row = int(not active_row)
        active_column = self._index % 2

        active_text = self._matrix[active_row].copy()
        active_text[active_column] = ('loading_active_block', active_text[active_column])
        old_text = self._matrix[old_row].copy()

        self._shape[old_row].set_text(old_text)
        self._shape[active_row].set_text(active_text)

class LoadingChatBox(urwid.Frame):
    def __init__(self, message, status_message=''):
        self._status_message = urwid.Text(status_message, align='center')
        self.circular_loading = CircularLoading()
        body = urwid.Filler(urwid.Pile([
            SlackBot(),
            urwid.Text(('loading_message', message), align='center'),
            self.circular_loading,
            self._status_message
        ]))
        super(LoadingChatBox, self).__init__(body)

    @property
    def status_message(self):
        return self._status_message.get_text()

    @status_message.setter
    def status_message(self, value):
        self._status_message.set_text(value)

class LoadingSideBar(urwid.Frame):
    def __init__(self):
        header = TextDivider(placeholder(size=12))
        divider = urwid.Divider('─')
        body = urwid.ListBox([
            urwid.Text(placeholder(size=20, left=2)),
            divider
        ] + [urwid.Text(placeholder(size=size, left=2))
            for size in [5, 7, 19, 8, 0, 3, 22, 14, 11, 13]])
        super(LoadingSideBar, self).__init__(body, header=header, footer=divider)

class SlackBot(urwid.Pile):
    _matrix = [
        [('   \uE0BA', 'white', 'h69'), (' ', 'white', 'white'), ('\uE0B8   ', 'white', 'h200')],
        [(' \uE0B2', 'white', 'h78'), ('\uF140 v \uF140', 'h91', 'white'), ('\uE0B0 ', 'white', 'h124')],
        [('   \uE0BE', 'white', 'h22'), (' ', 'white', 'white'), ('\uE0BC   ', 'white', 'h202')],
    ]

    def __init__(self):
        super(SlackBot, self).__init__([
            urwid.Text([
                (urwid.AttrSpec(pair[1], pair[2]), pair[0]) for pair in row
            ], align='center')
            for row in self._matrix
        ])

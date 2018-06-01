import urwid
from .components import TextDivider, options

def placeholder(size=10, left=0):
    return ((' ' * left)[:left] +
        (options['icons']['square'] * size)[:size])

class LoadingChatBox(urwid.Frame):
    def __init__(self):
        body = urwid.Filler(SlackBot())
        super(LoadingChatBox, self).__init__(body)

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
        [('    \uE0BA', 'white', 'h69'), (' ', 'white', 'white'), ('\uE0B8    ', 'white', 'h200')],
        [('  \uE0B2', 'white', 'h78'), ('\uF140 v \uF140', 'h91', 'white'), ('\uE0B0  ', 'white', 'h124')],
        [('    \uE0BE', 'white', 'h22'), (' ', 'white', 'white'), ('\uE0BC    ', 'white', 'h202')],
    ]

    def __init__(self):
        super(SlackBot, self).__init__([
            urwid.Text([
                (urwid.AttrSpec(pair[1], pair[2]), pair[0]) for pair in row
            ], align='center')
            for row in self._matrix
        ])
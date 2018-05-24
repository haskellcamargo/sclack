#!/usr/bin/env python3
import urwid

def exit_on_q(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()

palette = [
    ('app', '', '', '', 'h99', 'h235'),
    ('sidebar', '', '', '', 'white', 'h99')
]

class Sidebar(urwid.BoxWidget):
    def __init__(self):
        self.contents = urwid.SimpleListWalker([
            urwid.Text('NG Informatica ' + str(x)) for x in range(1, 100)
        ])
        self.listbox = urwid.LineBox(urwid.ListBox(self.contents), 'Channels', title_align='left')
        self.edit = False

    def render(self, size, focus=False):
        return self.listbox.render(size, focus)

    def keypress(self, size, key):
        self.listbox.keypress(size, key)

sidebar = urwid.AttrWrap(Sidebar(), 'sidebar')
columns = urwid.Columns([
    ('fixed', 25, sidebar)
], 1)

header= urwid.Text('foo')
footer= urwid.Text('bar')
app = urwid.Frame(urwid.AttrWrap(columns, 'app'))
loop = urwid.MainLoop(app, palette, unhandled_input=exit_on_q)
loop.screen.set_terminal_properties(colors=256)
loop.run()

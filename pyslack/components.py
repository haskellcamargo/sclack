import urwid

class Channel(urwid.AttrMap):
    def __init__(self, name, is_private=False):
        icon = ' · ' if is_private else ' # '
        body = urwid.SelectableIcon([icon, name])
        super(Channel, self).__init__(body, None, 'active_channel')

class SideBar(urwid.Frame):
    def __init__(self, channels=[], title=''):
        header = TextDivider(title)
        footer = urwid.Divider('─')
        empty_line = urwid.Divider(' ')
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker([
            empty_line,
            TextDivider('Channels'),
            *channels
        ]))
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

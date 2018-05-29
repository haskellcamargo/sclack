import urwid

class SideBar(urwid.Frame):
    def __init__(self, title=''):
        header = TextDivider('nginformatica')
        footer = urwid.Divider('─')
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker([
            urwid.AttrMap(urwid.Edit(str(x)), None, 'reveal focus') for x in range(1, 10)
        ]))
        super(SideBar, self).__init__(self.listbox, header=header, footer=footer)

class TextDivider(urwid.Columns):
    def __init__(self, text='', align='left', char='─'):
        text_size = len(text) + 2
        text_widget = urwid.Text(text, align='center')
        if align == 'right':
            body = [
                urwid.Divider(char),
                ('fixed', text_size, text_widget),
                ('fixed', 1, urwid.Divider(char))
            ]
        elif align == 'center':
            body = [
                urwid.Divider(char),
                ('fixed', text_size, text_widget),
                urwid.Divider(char)
            ]
        else:
            body = [
                ('fixed', 1, urwid.Divider(char)),
                ('fixed', text_size, text_widget),
                urwid.Divider(char)
            ]
        super(TextDivider, self).__init__(body)

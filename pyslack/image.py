import subprocess
import urwid

color_list = [
    'black',
    'dark red',
    'dark green',
    'brown',
    'dark blue',
    'dark magenta',
    'dark cyan',
    'light gray',
    'dark gray',
    'light red',
    'light green',
    'yellow',
    'light blue',
    'light magenta',
    'light cyan',
    'white'
]

def ansi_to_urwid(ansi_text):
    result = []
    ansi_text = ansi_text.decode('utf-8')
    for instruction in ansi_text.split('\x1B['):
        try:
            attr, text = instruction.split('m', 1)
        except:
            attr = '0'
            text = instruction.split('m', 1)
        attr_list = [int(code) for code in attr.split(';')]
        attr_list.sort()
        foreground = -1
        background = -1
        for attr in attr_list:
            if attr <= 29:
                pass
            elif attr <= 37:
                foreground = attr - 30
            elif attr <= 47:
                background = attr - 40
            elif attr <= 94:
                foreground = foreground + 8
            elif attr >= 100 and attr <= 104:
                background = background + 8
        foreground = color_list[foreground]
        background = color_list[background]
        result.append((urwid.AttrSpec(foreground, background), text))
    return result

def img_to_ansi(path, width, height):
    command = ['img2txt', path, '-f', 'utf8']
    if width:
        command.extend(['-W', str(width)])
    if height:
        command.extend(['-H', str(height)])
    ansi_text = subprocess.check_output(command)
    return ansi_text

class Image(urwid.Text):
    def __init__(self, path, width=None, height=None):
        self.markup = ansi_to_urwid(img_to_ansi(path, width, height))
        super(Image, self).__init__(self.markup)


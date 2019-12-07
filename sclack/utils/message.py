import os
import platform
import re
import shlex
import subprocess
import tempfile
from datetime import datetime

from ..store import Store


def format_date_time(ts):
    """
    Format date time for message
    :param ts:
    :return:
    """
    message_datetime = datetime.fromtimestamp(float(ts))
    message_date = message_datetime.date()
    today = datetime.today().date()

    if message_date == today:
        date_text = message_datetime.strftime('Today at %I:%M%p')
    else:
        date_text = message_datetime.strftime('%b %d, %Y at %I:%M%p')

    return date_text


def get_mentioned_patterns(user_id):
    """
    All possible pattern in message which mention me
    :param user_id:
    :type user_id: str
    :return:
    """
    slack_mentions = [
        '<!everyone>',
        '<!here>',
        '<!channel>',
        '<@{}>'.format(user_id),
    ]

    patterns = []

    for mention in slack_mentions:
        patterns.append('^{}[ ]+'.format(mention))
        patterns.append('^{}$'.format(mention))
        patterns.append('[ ]+{}'.format(mention))

    return re.compile('|'.join(patterns))


def edit_text_in_editor(initial_text):
    with tempfile.NamedTemporaryFile(suffix=".markdown") as fobj:
        fobj.write(initial_text.encode('utf-8'))
        fobj.flush()
        with Store.instance.interrupt_urwid_mainloop():
            _edit_file_in_editor(fobj.name)
        fobj.seek(0)
        return fobj.read().decode('utf-8')


def _edit_file_in_editor(filepath):
    editor = Store.instance.config['features'].get('editor', '')
    if not editor:
        editor = os.environ.get('EDITOR')
    if editor:
        cmd = ' '.join((editor, shlex.quote(filepath)))
        subprocess.call(cmd, shell=True)
    else:
        if platform.system() == 'Darwin':  # macOS
            subprocess.call(('open', filepath))
        elif platform.system() == 'Windows':  # Windows
            os.startfile(filepath)
        else:  # linux variants
            subprocess.call(('xdg-open', filepath))

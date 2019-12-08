# Notification wrapper

import os
import platform
import subprocess


def get_notifier():
    if platform.system() == 'Darwin':
        import pync
        pync.notify
    elif platform.system() == 'Linux':
        return linux_notify


def linux_notify(message, title=None, subtitle=None, appIcon=None, **kwargs):
    if subtitle:
        if title:
            title = f'{title} by {subtitle}'
        else:
            title = subtitle
    args = ['notify-send']
    if appIcon:
        args += ['--icon', appIcon]
    if title:
        args += [title]
    args += [message]
    try:
        subprocess.check_output(args, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pass  # Do not fail if notify-send is not available.


if __name__ == '__main__':
    """
    Test your notification availability
    """
    get_notifier()(
        'Your notification message is here',
        title='Sclack notification',
        subtitle='test',
        appIcon=os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', 'resources/slack_icon.png')
        ),
        sound='default',
    )

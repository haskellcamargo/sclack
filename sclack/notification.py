# Notification wrapper

import os
import platform
import subprocess


def notify(*args, **kargs):
    # Noop by default
    pass


if platform.system() == 'Darwin':
    try:
        import pync
    except ImportError:
        pass
    else:
        notify = pync.notify
elif platform.system() == 'Linux':

    def notify(message, title=None, subtitle=None, appIcon=None, **kwargs):
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
    notify(
        'Your notification message is here',
        title='Sclack notification',
        subtitle='test',
        appIcon=os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', 'resources/slack_icon.png')
        ),
        sound='default',
    )

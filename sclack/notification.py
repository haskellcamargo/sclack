# Notification wrapper

import platform
import subprocess
from pathlib import Path

APP_ICON = str((Path(__file__).parent.parent / 'resources' / 'slack_icon.png').resolve())


def notify(*args, **kargs):
    # Noop by default
    pass


if platform.system() == 'Darwin':
    try:
        import pync
    except ImportError:
        pass
    else:

        def notify(message, title, sender_name):
            pync.notify(
                message, title=title, subtitle=sender_name, appIcon=APP_ICON, sound='default'
            )


elif platform.system() == 'Linux':

    def notify(message, title, sender_name):
        args = ['notify-send', '--icon', APP_ICON, f'{title} by {sender_name}', message]
        try:
            subprocess.check_output(args, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            pass  # Do not fail if notify-send is not available.


if __name__ == '__main__':
    """
    Test your notification availability
    """
    notify('Your notification message is here', 'Sclack notification', 'test')

# Notification wrapper

import os
import platform
import subprocess
import sys


def notify(message, **kwargs):
    if platform.system() == 'Darwin':
        import pync

        pync.notify(message, **kwargs)
    elif platform.system() == 'Linux':
        pync = LinuxTerminalNotifier()
        pync.notify(message, **kwargs)
    else:
        # M$ Windows
        pass


class LinuxTerminalNotifier(object):
    def __init__(self):
        """
        Raises an exception if not supported on the current platform or
        if terminal-notifier was not found.
        """
        proc = subprocess.Popen(["which", "notify-send"], stdout=subprocess.PIPE)
        env_bin_path = proc.communicate()[0].strip()

        if env_bin_path and os.path.exists(env_bin_path):
            self.bin_path = os.path.realpath(env_bin_path)

        if not os.path.exists(self.bin_path):
            raise Exception("Notifier is not defined")

    def notify(self, message, title=None, subtitle=None, appIcon=None, **kwargs):
        if subtitle:
            if title:
                title = f'{title} by {subtitle}'
            else:
                title = subtitle
        args = []
        if appIcon:
            args += ['--icon', appIcon]
        if title:
            args += [title]
        args += [message]
        return self.execute(args)

    def execute(self, args):
        args = [str(arg) for arg in args]

        output = subprocess.Popen(
            [self.bin_path] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        if output.returncode:
            raise Exception("Some error during subprocess call.")

        return output


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

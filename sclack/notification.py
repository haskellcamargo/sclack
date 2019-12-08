# Notification wrapper

import os
import platform
import subprocess
import sys


class TerminalNotifier(object):
    def notify(self, message, **kwargs):
        if platform.system() == 'Darwin':
            import pync

            pync.notify(message, **kwargs)
        elif platform.system() == 'Linux':
            new_kwargs = {}
            mappings = {
                'group': 'category',
                'appIcon': 'icon',
                'title': 'title',
                'subtitle': 'subtitle',
            }

            for origin_attr, new_attr in mappings.items():
                if kwargs.get(origin_attr):
                    new_kwargs[new_attr] = kwargs.get(origin_attr)

            if kwargs.get('subtitle'):
                if new_kwargs.get('title'):
                    title = '{} by '.format(new_kwargs['title'])
                else:
                    title = ''

                new_kwargs['title'] = '{}{}'.format(title, kwargs.get('subtitle'))

            pync = LinuxTerminalNotifier()
            pync.notify(message, **new_kwargs)
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

    def notify(self, message, **kwargs):
        if sys.version_info < (3,):
            message = message.encode('utf-8')

        args = []

        if kwargs.get('icon'):
            args += ['--icon', kwargs['icon']]

        if kwargs.get('title'):
            args += [kwargs['title'], message]
        else:
            args += [message]

        return self.execute(args)

    def execute(self, args):
        args = [str(arg) for arg in args]

        output = subprocess.Popen(
            [self.bin_path,] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        if output.returncode:
            raise Exception("Some error during subprocess call.")

        return output


if __name__ == '__main__':
    """
    Test your notification availability
    """
    TerminalNotifier().notify(
        'Your notification message is here',
        title='Sclack notification',
        appIcon=os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', 'resources/slack_icon.png')
        ),
    )

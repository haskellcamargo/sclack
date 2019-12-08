# Notification wrapper

import asyncio
import platform
from functools import partial
from pathlib import Path

APP_ICON = str((Path(__file__).parent.parent / 'resources' / 'slack_icon.png').resolve())


async def noop(*args, **kargs):
    # Noop by default
    pass


if platform.system() == 'Darwin':
    try:
        import pync
    except ImportError:
        notiy = noop
    else:

        async def notify(message, title, sender_name):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(
                    pync.notify,
                    message,
                    title=title,
                    subtitle=sender_name,
                    appIcon=APP_ICON,
                    sound='default',
                ),
            )


elif platform.system() == 'Linux':

    async def notify(message, title, sender_name):
        await asyncio.create_subprocess_exec(
            'notify-send',
            '--icon',
            APP_ICON,
            f'{title} by {sender_name}',
            message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )


else:
    notify = noop


if __name__ == '__main__':
    """
    Test your notification availability
    """
    notify('Your notification message is here', 'Sclack notification', 'test')

from datetime import datetime

import urwid


class Time(urwid.Text):
    def __init__(self, timestamp):
        time = datetime.fromtimestamp(float(timestamp)).strftime('%H:%M')
        super(Time, self).__init__(('datetime', ' {} '.format(time)))

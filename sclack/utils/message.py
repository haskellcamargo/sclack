import re
from datetime import datetime


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

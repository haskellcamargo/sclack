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

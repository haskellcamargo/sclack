def get_group_name(group_raw_name):
    """
    TODO Remove last number
    :param group_raw_name:
    :return:
    """
    if group_raw_name[:5] == 'mpdm-':
        group_parts = group_raw_name[5:].split('--')
        group_parts = ['@{}'.format(item) for item in group_parts]
        return ', '.join(group_parts)

    return group_raw_name


def is_channel(channel_id):
    """
    Is a channel
    :param channel_id:
    :return:
    """
    return channel_id[0] == 'C'


def is_dm(channel_id):
    """
    Is direct message
    :param channel_id:
    :return:
    """
    return channel_id[0] == 'D'


def is_group(channel_id):
    """
    Is a group
    :param channel_id:
    :return:
    """
    return channel_id[0] == 'G'

from sclack.app import ask_for_token
from sclack.quick_switcher import remove_diacritic
from slackclient import SlackClient


def get_config():
    json_config = {}
    ask_for_token(json_config)
    return json_config

def get_token():
    json_config = get_config()
    return json_config['workspaces']['default']

def get_slack_client():
    return SlackClient(get_token())

def test_workspace_token(): 
    json_config = get_config()
    assert json_config.get('workspaces', None) != None

def test_auth():
    client = get_slack_client()
    auth = client.api_call('auth.test')
    assert (auth != None) and (auth.get('ok', False) == True)


def test_get_channels():
    client = get_slack_client()
    channels = client.api_call('users.conversations',
            exclude_archived=True,
            limit=10,  # 1k is max limit
            types='public_channel,private_channel,im')
    assert channels != None and channels.get('error', None) == None

def test_get_members():
    client = get_slack_client()
    channels = client.api_call('users.conversations',
            exclude_archived=True,
            limit=10,  # 1k is max limit
            types='public_channel,private_channel,im')
    members = client.api_call('conversations.members', channel=channels['channels'][0]['id'])
    assert members != None and members.get('error', None) == None

def test_get_members_pagination1():
    client = get_slack_client()
    channels = client.api_call('users.conversations',
            exclude_archived=True,
            limit=10,  # 1k is max limit
            types='public_channel,private_channel,im')
    members = client.api_call('conversations.members', channel=channels['channels'][0]['id'], limit=1000)
    assert members != None and members.get('response_metadata', None) != None

def test_get_members_pagination2():
    client = get_slack_client()
    channels = client.api_call('users.conversations',
            exclude_archived=True,
            limit=10,  # 1k is max limit
            types='public_channel,private_channel,im')
    members = client.api_call('conversations.members', channel=channels['channels'][0]['id'], limit=1)
    assert members != None and members.get('response_metadata', None) != None
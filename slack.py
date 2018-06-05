    def find_bot(id, users):
        return next(filter(lambda user: user.get('is_bot', False) and user['profile']['bot_id'] == id, users), None)

    # _messages = []
    # Bots cache
    _bots = {}
    for message in messages:
        if message.get('subtype', None) == 'bot_message':
            bot = find_bot(message['bot_id'], members)
            if bot:
                user_name = bot['profile']['display_name']
            elif message['bot_id'] in _bots:
                # Use bot data from cache
                bot = _bots.get(message['bot_id'])
                user_name = bot['name']
            else:
                bot = slack.api_call('bots.info', bot=message['bot_id'])['bot']
                _bots[message['bot_id']] = bot
                user_name = bot['name']

            is_app = 'app_id' in bot
            color = '#{}'.format(shorten_hex(bot.get('color', '333333')))
        else:
            is_app = False
            # user = find_user(message['user'], members)
            # user_name = user['profile']['display_name']
            # color = '#{}'.format(shorten_hex(user.get('color', '333333')))

        file = message.get('file')
        if file and file.get('filetype', None) in ('jpg', 'png', 'gif', 'jpeg', 'bmp'):
            file = Image(token=token, path=file['url_private'])
        else:
            file = None

        attachments = [
            Attachment(
                fields=attachment.get('fields'), color='#{}'.format(
                    shorten_hex(attachment.get('color', 'CCCCCC'))
                ),
                pretext=attachment.get('pretext')
            )
            for attachment in message.get('attachments', [])
        ]

        # time = Time(message['ts'])
        # text = MarkdownText(message['text'])
        # is_edited = 'edited' in message
        # is_starred = message.get('is_starred', False)
        # reactions = list(map(
            # lambda reaction: Reaction(name=reaction['name'], count=reaction['count']),
            # message.get('reactions', [])
        # ))

        # user = User(name=user_name, color=color, is_app=is_app)
        # indicators = Indicators(is_edited=is_edited, is_starred=is_starred)

        # _messages.append(Message(
        #     time=time,
        #     user=user,
        #     text=text,
        #     indicators=indicators,
        #     reactions=reactions,
        #     file=file,
        #     attachments=attachments
        # ))

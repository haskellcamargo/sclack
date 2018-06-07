
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

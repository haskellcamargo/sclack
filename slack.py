
        attachments = [
            Attachment(
                fields=attachment.get('fields'), color='#{}'.format(
                    shorten_hex(attachment.get('color', 'CCCCCC'))
                ),
                pretext=attachment.get('pretext')
            )
            for attachment in message.get('attachments', [])
        ]

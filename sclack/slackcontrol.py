import slack


class RTMClient(slack.RTMClient):
    def __init__(self, app, *, token, **kwargs):
        self.app = app
        super(RTMClient, self).__init__(token=token, run_aync=True, auto_reconnect=True, **kwargs)


@RTMClient.run_on(event='channel_marked')
async def channel_marked(rtm_client, channel, unread_count_display=0, **kwargs):
    app = rtm_client.app
    targets = app.sidebar.get_all_channels()
    mark_unread_targets(channel, targets, unread_count_display)


@RTMClient.run_on(event='group_marked')
async def group_marked(rtm_client, channel, unread_count_display=0, **kwargs):
    app = rtm_client.app
    targets = app.sidebar.get_all_groups()
    mark_unread_targets(channel, targets, unread_count_display)


@RTMClient.run_on(event='im_marked')
async def im_marked(rtm_client, channel, unread_count_display=0, **kwargs):
    app = rtm_client.app
    targets = app.sidebar.get_all_dms()
    mark_unread_targets(channel, targets, unread_count_display)


def mark_unread_targets(channel_id, targets, unread):
    for target in targets:
        if target.id == channel_id:
            target.set_unread(unread)


@RTMClient.run_on(event='message')
async def message(rtm_client, loop, **event):
    app = rtm_client.app
    loop.create_task(app.update_chat(event.get('channel')))
    await update_message(app, **event)

    if (
        event.get('subtype') != 'message_deleted'
        and event.get('subtype') != 'message_changed'
        and not event.get('hidden')
    ):
        # Continue while notifications are displayed asynchronuously.
        loop.create_task(
            app.notify_message(event.get('channel'), event.get('text'), event.get('user'))
        )


async def update_message(app, **event):
    if event.get('channel') == app.store.state.channel['id']:
        if not app.is_chatbox_rendered:
            return

        if event.get('subtype') == 'message_deleted':
            delete_message(app, **event)
        elif event.get('subtype') == 'message_changed':
            await change_message(app, **event)
        elif event.get('hidden'):
            pass
        else:
            messages = await app.render_messages([event])
            app.chatbox.body.body.extend(messages)
            app.chatbox.body.scroll_to_bottom()


def delete_message(app, delete_ts=None, **kwargs):
    for widget in app.chatbox.body.body:
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == delete_ts:
            app.chatbox.body.body.remove(widget)
            break


async def change_message(app, message, **kwargs):
    for index, widget in enumerate(app.chatbox.body.body):
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == message['ts']:
            app.chatbox.body.body[index] = await app.render_message(message)
            break


@RTMClient.run_on(event='user_typing')
async def user_typing(rtm_client, channel=None, user=None, **kwargs):
    app = rtm_client.app
    if not app.is_chatbox_rendered:
        return

    if channel == app.store.state.channel['id']:
        user = app.store.find_user_by_id(user)
        name = app.store.get_user_display_name(user)

        app.chatbox.message_box.typing = name
        app.urwid_loop.set_alarm_in(3, app.stop_typing)


@RTMClient.run_on(event='dnd_updated')
async def dnd_updated(rtm_client, dnd_status=None, **kwargs):
    if not dnd_status:
        return
    app = rtm_client.app
    app.store.state.is_snoozed = dnd_status['snooze_enabled']
    app.sidebar.profile.set_snooze(app.store.state.is_snoozed)


async def other(app, text, ts, **kwargs):
    if not app.is_chatbox_rendered:
        return

    # Message was sent, Slack confirmed it.
    messages = await app.render_messages(
        [{'text': text, 'ts': ts, 'user': app.store.state.auth['user_id'],}]
    )
    app.chatbox.body.body.extend(messages)
    app.chatbox.body.scroll_to_bottom()
    app.handle_mark_read(-1)

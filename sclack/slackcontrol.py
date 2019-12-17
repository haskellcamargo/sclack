import asyncio


async def start(app, loop):
    app.store.slack.rtm_connect(auto_reconnect=True)

    while app.store.slack.server.connected is True:
        events = app.store.slack.rtm_read()

        for event in events:
            if event.get('type') == 'channel_marked':
                loop.create_task(channel_marked(app, **event))
            elif event.get('type') == 'group_marked':
                loop.create_task(group_marked(app, **event))
            elif event.get('type') == 'im_marked':
                loop.create_task(im_marked(app, **event))
            elif event['type'] == 'message':
                loop.create_task(message(app, loop, **event))
            elif event['type'] == 'user_typing':
                loop.create_task(user_typing(app, **event))
            elif event.get('type') == 'dnd_updated':
                loop.create_task(dnd_updated(app, **event))
            elif event.get('ok', False):
                loop.create_task(other(app, **event))
        await asyncio.sleep(0.5)


async def channel_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_channels()
    mark_unread_targets(channel, targets, unread_count_display)


async def group_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_groups()
    mark_unread_targets(channel, targets, unread_count_display)


async def im_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_dms()
    mark_unread_targets(channel, targets, unread_count_display)


def mark_unread_targets(channel_id, targets, unread):
    for target in targets:
        if target.id == channel_id:
            target.set_unread(unread)


async def message(app, loop, **event):
    loop.create_task(app.update_chat(event.get('channel')))
    update_message(app, **event)

    if event.get('subtype') != 'message_deleted' and event.get('subtype') != 'message_changed':
        # Continue while notifications are displayed asynchronuously.
        loop.create_task(
            app.notify_message(event.get('channel'), event.get('text'), event.get('user'))
        )


def update_message(app, **event):
    if event.get('channel') == app.store.state.channel['id']:
        if not app.is_chatbox_rendered:
            return

        if event.get('subtype') == 'message_deleted':
            delete_message(app, **event)
        elif event.get('subtype') == 'message_changed':
            change_message(app, **event)
        else:
            app.chatbox.body.body.extend(app.render_messages_([event]))
            app.chatbox.body.scroll_to_bottom()


def delete_message(app, delete_ts, **kwargs):
    for widget in app.chatbox.body.body:
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == delete_ts:
            app.chatbox.body.body.remove(widget)
            break


def change_message(app, message, **kwargs):
    for index, widget in enumerate(app.chatbox.body.body):
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == message['ts']:
            app.chatbox.body.body[index] = app.render_message_(message)
            break


async def user_typing(app, channel=None, user=None, **kwargs):
    if not app.is_chatbox_rendered:
        return

    if channel == app.store.state.channel['id']:
        user = app.store.find_user_by_id(user)
        name = app.store.get_user_display_name(user)

        app.chatbox.message_box.typing = name
        app.urwid_loop.set_alarm_in(3, app.stop_typing)


async def dnd_updated(app, dnd_status=None, **kwargs):
    if not dnd_status:
        return
    app.store.state.is_snoozed = dnd_status['snooze_enabled']
    app.sidebar.profile.set_snooze(app.store.state.is_snoozed)


async def other(app, text, ts, **kwargs):
    if not app.is_chatbox_rendered:
        return

    # Message was sent, Slack confirmed it.
    app.chatbox.body.body.extend(
        app.render_messages_([{'text': text, 'ts': ts, 'user': app.store.state.auth['user_id'],}])
    )
    app.chatbox.body.scroll_to_bottom()
    app.handle_mark_read(-1)

import asyncio


async def start(app, loop):
    app.store.slack.rtm_connect(auto_reconnect=True)

    def stop_typing(*args):
        # Prevent error while switching workspace
        if app.is_chatbox_rendered:
            app.chatbox.message_box.typing = None

    while app.store.slack.server.connected is True:
        events = app.store.slack.rtm_read()

        for event in events:
            if event.get('type') == 'channel_marked':
                channel_marked(app, **event)
            elif event.get('type') == 'group_marked':
                group_marked(app, **event)
            elif event.get('type') == 'im_marked':
                im_marked(app, **event)
            elif event['type'] == 'message':
                message(app, loop, **event)
            elif event['type'] == 'user_typing':
                user_typing(app, stop_typing, **event)
            elif event.get('type') == 'dnd_updated' and 'dnd_status' in event:
                dnd_updated(app, **event)
            elif event.get('ok', False):
                other(app, **event)
        await asyncio.sleep(0.5)


def channel_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_channels()
    mark_unread_targets(channel, targets, unread_count_display)


def group_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_groups()
    mark_unread_targets(channel, targets, unread_count_display)


def im_marked(app, channel, unread_count_display=0, **kwargs):
    targets = app.sidebar.get_all_dms()
    mark_unread_targets(channel, targets, unread_count_display)


def mark_unread_targets(channel_id, targets, unread):
    for target in targets:
        if target.id == channel_id:
            target.set_unread(unread)


def message(app, loop, **event):
    loop.create_task(app.update_chat(event))
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
            app.chatbox.body.body.extend(app.render_messages([event]))
            app.chatbox.body.scroll_to_bottom()


def delete_message(app, delete_ts, **kwargs):
    for widget in app.chatbox.body.body:
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == delete_ts:
            app.chatbox.body.body.remove(widget)
            break


def change_message(app, message, **kwargs):
    for index, widget in enumerate(app.chatbox.body.body):
        if hasattr(widget, 'ts') and getattr(widget, 'ts') == message['ts']:
            app.chatbox.body.body[index] = app.render_message(message)
            break


def user_typing(app, stop_typing, channel=None, user=None, **kwargs):
    if not app.is_chatbox_rendered:
        return

    if channel == app.store.state.channel['id']:
        user = app.store.find_user_by_id(user)
        name = app.store.get_user_display_name(user)

        app.chatbox.message_box.typing = name
        app.urwid_loop.set_alarm_in(3, stop_typing)


def dnd_updated(app, dnd_status, **kwargs):
    app.store.state.is_snoozed = dnd_status['snooze_enabled']
    app.sidebar.profile.set_snooze(app.store.state.is_snoozed)


def other(app, text, ts, **kwargs):
    if not app.is_chatbox_rendered:
        return

    # Message was sent, Slack confirmed it.
    app.chatbox.body.body.extend(
        app.render_messages([{'text': text, 'ts': ts, 'user': app.store.state.auth['user_id'],}])
    )
    app.chatbox.body.scroll_to_bottom()
    app.handle_mark_read(-1)

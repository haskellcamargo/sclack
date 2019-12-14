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
                targets = app.sidebar.get_all_channels()
                mark_unread_targets(event['channel'], targets, event.get('unread_count_display', 0))
            elif event.get('type') == 'group_marked':
                targets = app.sidebar.get_all_groups()
                mark_unread_targets(event['channel'], targets, event.get('unread_count_display', 0))
            elif event.get('type') == 'im_marked':
                targets = app.sidebar.get_all_dms()
                mark_unread_targets(event['channel'], targets, event.get('unread_count_display', 0))
            elif event['type'] == 'message':
                loop.create_task(app.update_chat(event))

                if event.get('channel') == app.store.state.channel['id']:
                    if not app.is_chatbox_rendered:
                        return

                    if event.get('subtype') == 'message_deleted':
                        for widget in app.chatbox.body.body:
                            if (
                                hasattr(widget, 'ts')
                                and getattr(widget, 'ts') == event['deleted_ts']
                            ):
                                app.chatbox.body.body.remove(widget)
                                break
                    elif event.get('subtype') == 'message_changed':
                        for index, widget in enumerate(app.chatbox.body.body):
                            if (
                                hasattr(widget, 'ts')
                                and getattr(widget, 'ts') == event['message']['ts']
                            ):
                                app.chatbox.body.body[index] = app.render_message(event['message'])
                                break
                    else:
                        app.chatbox.body.body.extend(app.render_messages([event]))
                        app.chatbox.body.scroll_to_bottom()
                if (
                    event.get('subtype') != 'message_deleted'
                    and event.get('subtype') != 'message_changed'
                ):
                    # Continue while notifications are displayed asynchronuously.
                    loop.create_task(app.notify_message(event))
            elif event['type'] == 'user_typing':
                if not app.is_chatbox_rendered:
                    return

                if event.get('channel') == app.store.state.channel['id']:
                    user = app.store.find_user_by_id(event['user'])
                    name = app.store.get_user_display_name(user)

                    app.chatbox.message_box.typing = name
                    app.urwid_loop.set_alarm_in(3, stop_typing)
            elif event.get('type') == 'dnd_updated' and 'dnd_status' in event:
                app.store.state.is_snoozed = event['dnd_status']['snooze_enabled']
                app.sidebar.profile.set_snooze(app.store.state.is_snoozed)
            elif event.get('ok', False):
                if not app.is_chatbox_rendered:
                    return

                # Message was sent, Slack confirmed it.
                app.chatbox.body.body.extend(
                    app.render_messages(
                        [
                            {
                                'text': event['text'],
                                'ts': event['ts'],
                                'user': app.store.state.auth['user_id'],
                            }
                        ]
                    )
                )
                app.chatbox.body.scroll_to_bottom()
                app.handle_mark_read(-1)
        await asyncio.sleep(0.5)


def mark_unread_targets(channel_id, targets, unread):
    for target in targets:
        if target.id == channel_id:
            target.set_unread(unread)

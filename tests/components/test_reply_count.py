from sclack.components import ReplyCount


def test_display_text_for_single_reply():
    reply_count = ReplyCount(1)
    assert reply_count.text == '1 reply'


def test_display_text_for_multiple_replies():
    reply_count = ReplyCount(12)
    assert reply_count.text == '12 replies'

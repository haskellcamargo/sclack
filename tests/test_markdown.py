from sclack.markdown import MarkdownText
from sclack.store import Store

def create_markdown():
    workspaces = [["a", "b"]]
    config = {
      "features": {
        "markdown": True,
        "emoji": {}
      }
    }
    store = Store(workspaces, config)
    Store.instance = store
    return MarkdownText("")

def parse_message(msg):
    mt = create_markdown()
    return mt.parse_message(msg)

def test_non_markdown():
    assert parse_message("foo") == [("message","foo")]

def test_html_entity_conversion():
    assert parse_message("&amp; &lt; &gt;") == [("message","& < >")]

def test_markdown():
    assert parse_message("*something bold*") == [
      ("message", ""), ("bold","something bold"), ("message", "")
    ]

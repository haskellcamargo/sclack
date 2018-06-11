import urwid
from .store import Store

class MarkdownText(urwid.SelectableIcon):
    _buffer = ''
    _state = 'message'
    _previous_state = 'message'
    _result = []

    def __init__(self, text):
        self.original_text = text
        if Store.instance.config['features']['markdown']:
            self.markup = self.parse_message(text)
        else:
            self.markup = [('message', text)]
        super(MarkdownText, self).__init__(self.markup)

    def decode_buffer(self):
        return (self._buffer
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&amp;', '&'))

    def change_state(self, buffer_state, next_state):
        self._result.append((buffer_state, self.decode_buffer()))
        self._buffer = ''
        self._previous_state = self._state
        self._state = next_state

    def resolve_mention(self):
        if self._buffer.startswith('@'):
            user = Store.instance.find_user_by_id(self._buffer[1:])
            if user:
                self._buffer = user.get('real_name', user['name'])

    def parse_message(self, text):
        self._buffer = ''
        self._state = 'message'
        self._previous_state = 'message'
        self._result = []

        text = text.replace('```', '`')
        for char in text:
            if char == '<' and self._state != 'code':
                self.change_state('message', 'link')
            elif char == '>' and self._state == 'link':
                self.resolve_mention()
                self.change_state('link', 'message')
            elif char == '|' and self._state == 'link':
                self._buffer = ''
            elif char == '*' and self._state == 'bold':
                self.change_state('bold', self._previous_state)
            elif char == '*' and self._state not in ('link', 'code'):
                self.change_state(self._state, 'bold')
            elif char == '_' and self._state == 'italics':
                self.change_state('italics', self._previous_state)
            elif char == '_' and self._state not in ('link', 'code'):
                self.change_state(self._state, 'italics')
            elif char == '`' and self._state == 'code':
                self.change_state('code', self._previous_state)
            elif char == '`' and self._state != 'link':
                self.change_state(self._state, 'code')
            else:
                self._buffer = self._buffer + char

        self._result.append(('message', self.decode_buffer()))
        return self._result

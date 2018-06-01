import urwid

class MarkdownText(urwid.SelectableIcon):
    _buffer = ''
    _state = 'message'
    _previous_state = 'message'
    _result = []

    def __init__(self, text):
        self.markup = self.parse_message(text)
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

    def parse_message(self, text):
        self._buffer = ''
        self._state = 'message'
        self._previous_state = 'message'
        self._result = []

        for char in text:
            if char == '<':
                self.change_state('message', 'link')
            elif char == '>' and self._state == 'link':
                self.change_state('link', 'message')
            elif char == '|' and self._state == 'link':
                self._buffer = ''
            elif char == '*' and self._state == 'bold':
                self.change_state('bold', self._previous_state)
            elif char == '*' and self._state not in ('link', 'code'):
                self.change_state(self._previous_state, 'bold')
            elif char == '_' and self._state == 'italics':
                self.change_state('italics', self._previous_state)
            elif char == '_' and self._state not in ('link', 'code'):
                self.change_state(self._previous_state, 'italics')
            elif char == '`' and self._state == 'code':
                self.change_state('code', self._previous_state)
            elif char == '`' and self._state != 'link':
                self.change_state(self._previous_state, 'code')
            else:
                self._buffer = self._buffer + char

        self._result.append(('message', self.decode_buffer()))
        return self._result

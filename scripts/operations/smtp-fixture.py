"""Local rehearsal SMTP sink. Never forward mail; persist only synthetic messages in /mailbox."""
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
import json
import socketserver
import time

class SMTP(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 synthetic-mailbox\r\n')
        while line := self.rfile.readline(65536):
            verb = line.split(b' ', 1)[0].strip().upper()
            if verb in {b'EHLO', b'HELO'}:
                self.wfile.write(b'250 synthetic-mailbox\r\n')
            elif verb == b'DATA':
                self.wfile.write(b'354 send data\r\n')
                parts = []
                while True:
                    part = self.rfile.readline(65536)
                    if part in {b'.\r\n', b''}: break
                    parts.append(part[1:] if part.startswith(b'..') else part)
                    if sum(map(len, parts)) > 1024 * 1024: return
                message = BytesParser(policy=default).parsebytes(b''.join(parts))
                Path('/mailbox', f'{time.time_ns()}.json').write_text(json.dumps({'to': message['To'], 'body': message.get_content()}))
                self.wfile.write(b'250 accepted\r\n')
            elif verb == b'QUIT':
                self.wfile.write(b'221 bye\r\n'); return
            else:
                self.wfile.write(b'250 ok\r\n')

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('0.0.0.0', 1025), SMTP) as server:
    server.serve_forever()

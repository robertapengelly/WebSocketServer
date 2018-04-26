#-------------------------------------------------------------------------------------
#
#   Copyright 2018 Robert Pengelly.
#
#   This file is part of WebSocketServer.
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#-------------------------------------------------------------------------------------

#!/usr/bin/env python
# coding: utf-8

from    collections     import  deque

import  base64
import  codecs
import  errno
import  hashlib
import  re
import  socket
import  struct
import  sys

VER = sys.version_info[0]

if VER >= 3:
    import  socketserver
    from    http.server     import  BaseHTTPRequestHandler
    from    io              import  BytesIO, StringIO
else:
    import  SocketServer
    from    BaseHTTPServer  import  BaseHTTPRequestHandler
    from    StringIO        import  StringIO

def _check_unicode(val):
    if VER >= 3:
        return isinstance(val, str)
    else:
        return isinstance(val, unicode)

HANDSHAKE_STR = (
    "HTTP/1.1 101 Switching Protocols\r\n"
    "Upgrade: WebSocket\r\n"
    "Connection: Upgrade\r\n"
    "Sec-WebSocket-Accept: %(acceptstr)s\r\n\r\n"
)

GUID_STR = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


_VALID_STATUS_CODES = [1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011, 3000, 3999, 4000, 4999]

STREAM          = 0x00
TEXT            = 0x01
BINARY          = 0x02
CLOSE           = 0x08
PING            = 0x09
PONG            = 0x0A

HEADERB1        = 1
HEADERB2        = 3
LENGTHSHORT     = 4
LENGTHLONG      = 5
MASK            = 6
PAYLOAD         = 7

MAXHEADER       = 65536
MAXPAYLOAD      = 33554432

class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        if VER >= 3:
            self.rfile = BytesIO(request_text)
        else:
            self.rfile = StringIO(request_text)
        
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

class WebSocket(object):
    def __init__(self, master, sock, address):
        self.master = master
        self.sock = sock
        self.address = address
        self.fileno = sock.fileno()
        
        self.handshaked = False
        self.headerbuffer = bytearray()
        self.headertoread = 2048
        
        self.fin = 0
        self.data = bytearray()
        self.opcode = 0
        self.hasmask = 0
        self.maskarray = None
        self.length = 0
        self.lengtharray = None
        self.index = 0
        self.request = None
        self.usingssl = False
        
        self.frag_start = False
        self.frag_type = BINARY
        self.frag_buffer = None
        self.frag_decoder = codecs.getincrementaldecoder('utf-8')(errors='strict')
        self.closed = False
        self.sendq = deque()
        
        self.state = HEADERB1
        
        #======================================================================
        # Restrict the size of header and payload for security reasons.
        #======================================================================
        self.maxheader = MAXHEADER
        self.maxpayload = MAXPAYLOAD
    
    def _do_handshake(self, data):
        #==================================================================
        # Accumulate.
        #==================================================================
        self.headerbuffer.extend(data)
        
        if len(self.headerbuffer) >= self.maxheader:
            raise Exception('errro: header exceeded allowable size')
        
        #==================================================================
        # Indictaes end of HTTP header.
        #==================================================================
        if b'\r\n\r\n' in self.headerbuffer:
            self.request = HTTPRequest(self.headerbuffer)
            
            #==============================================================
            # Handshake RFC 6455
            #==============================================================
            try:
                match = re.compile('GET (.*) HTTP')
                match = match.search(self.headerbuffer.decode('utf-8'))
                
                if match is not None and len(match.groups()) == 1:
                    self.resource = match.group(1)
                else:
                    self.response = 'HTTP/1.1 405 Method Not Allowed\r\n\r\n'
                
                headers = self.request.headers
                
                if not 'Host' in headers:
                    self.response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                
                if not 'Upgrade' in headers or not headers['Upgrade'] == 'websocket':
                    self.response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                
                if not 'Connection' in headers or headers['Connection'].find('Upgrade') == -1:
                    self.response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                
                if not 'Sec-WebSocket-Key' in headers:
                    self.response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                
                if not 'Sec-WebSocket-Version' in headers or not headers['Sec-WebSocket-Version'] == '13':
                    self.response = 'HTTP/1.1 426 Upgrade Required\r\nSec-WebSocketVersion: 13\r\n\r\n'
                
                if hasattr(self, 'response'):
                    try:
                        close_msg = bytearray()
                        close_msg.extend(struct.pack('!H', 1000))
                        
                        if _check_unicode(self.response):
                            close_msg.extend(self.response.encode('utf-8'))
                        else:
                            close_msg.extend(self.response)
                        
                        self._send_message(False, CLOSE, close_msg)
                    finally:
                        return
                
                key = headers['Sec-WebSocket-Key']
                key = key.encode('ascii') + GUID_STR.encode('ascii')
                key = base64.b64encode(hashlib.sha1(key).digest()).decode('ascii')
                hstr = HANDSHAKE_STR % {'acceptstr': key}
                
                self.sendq.append((BINARY, hstr.encode('ascii')))
                self.handshaked = True
                self.handle_connected()
            except Exception as ex:
                raise Exception('error: handshake failed: %s' % str(ex))
    
    def _handle_close(self):
        status = 1000
        reason = u''
        length = len(self.data)
        
        if length == 0:
            pass
        elif length >= 2:
            status = struct.unpack_from('!H', self.data[:2])[0]
            reason = self.data[2:]
            
            if status not in _VALID_STATUS_CODES:
                status = 1002
            
            if len(reason) > 0:
                try:
                    reason = reason.decode('utf-8', errors='strict')
                except:
                    status = 1002
        else:
            status = 1002
        
        try:
            close_msg = bytearray()
            close_msg.extend(struct.pack('!H', status))
            
            if _check_unicode(reason):
                close_msg.extend(reason.encode('utf-8'))
            else:
                close_msg.extend(reason)
            
            self._send_message(False, CLOSE, close_msg)
        finally:
            pass
    
    def _handle_data(self):
        if self.handshaked is False:
            #==================================================================
            # Do the HTTP header and handshake.
            #==================================================================
            data = self.sock.recv(self.headertoread)
            
            if not data:
                raise Exception('info: remote socket closed')
            
            self._do_handshake(data)
        else:
            data = self.sock.recv(16384)
            
            if not data:
                raise Exception('info: remote socket closed')
            
            if VER >= 3:
                for d in data:
                    self._parse_message(d)
            else:
                for d in data:
                    self._parse_message(ord(d))
    
    def _handle_packet(self):
        if self.opcode == BINARY:
            pass
        elif self.opcode == CLOSE:
            pass
        elif self.opcode == STREAM:
            pass
        elif self.opcode == TEXT:
            pass
        elif self.opcode == PONG or self.opcode == PING:
            if len(self.data) > 125:
                raise Exception('error: control frame length can not be > 125')
        else:
            #==================================================================
            # Unknown or reserved opcode so just close.
            #==================================================================
            raise Exception('error: unknown opcode')
        
        if self.opcode == CLOSE:
            self._handle_close()
        elif self.fin == 0:
            self._handle_no_fin()
        else:
            self._handle_other()
    
    def _handle_no_fin(self):
        if self.opcode != STREAM:
            if self.opcode == PING or self.opcode == PONG:
                raise Exception('error: control messages can not be fragmented')
            
            self.frag_type = self.opcode
            self.frag_start = True
            self.frag_decoder.reset()
            
            if self.frag_type == TEXT:
                self.frag_buffer = []
                utf_str = self.frag_decoder.decode(self.data, final=False)
                
                if utf_str:
                    self.frag_buffer.append(utf_str)
            else:
                self.frag_buffer = bytearray()
                self.frag_buffer.extend(self.data)
        else:
            if self.frag_start is False:
                raise Exception('error: fragmentation protocol error')
            
            if self.frag_type == TEXT:
                utf_str = self.frag_decoder.decode(self.data, final = False)
                
                if utf_str:
                    self.frag_buffer.append(utf_str)
                else:
                    self.frag_buffer.extend(self.data)
    
    def _handle_other(self):
        if self.opcode == STREAM:
            if self.frag_start is False:
                raise Exception('error: fragmentation protocol error')
            
            if self.frag_type == TEXT:
                utf_str = self.frag_decoder.decode(self.data, final=True)
                self.frag_buffer.append(utf_str)
                self.data = u''.join(self.frag_buffer)
            else:
                self.frag_buffer.extend(self.data)
                self.data = self.frag_buffer
            
            self.handle_message()
            
            self.frag_decoder.reset()
            self.frag_type = BINARY
            self.frag_start = False
            self.frag_buffer = None
        elif self.opcode == PING:
            self._sendMessage(False, PONG, self.data)
        elif self.opcode == PONG:
            pass
        else:
            if self.frag_start is True:
                raise Exception('error: fragmentation protocol error')
            
            if self.opcode == TEXT:
                try:
                    self.data = self.data.decode('utf8', errors='strict')
                except Exception as exp:
                    raise Exception('error: invalid utf-8 payload')
            
            self.handle_message()
    
    def _header_b1(self, byte):
        self.fin = byte & 0x80
        self.opcode = byte & 0x0F
        self.state = HEADERB2
        
        self.index = 0
        self.length = 0
        self.lengtharray = bytearray()
        self.data = bytearray()
        
        rsv = byte & 0x70
        
        if rsv != 0:
            raise Exception('error: RSV bit must be 0')
    
    def _header_b2(self, byte):
        mask = byte & 0x80
        length = byte & 0x7F
        
        if self.opcode == PING and length > 125:
            raise Exception('error: ping packet is too large')
        
        if mask == 128:
            self.hasmask = True
        else:
            self.hasmask = False
        
        if length <= 125:
            self.length = length
            
            #==================================================================
            # If we have a mask we must read it.
            #==================================================================
            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                #==============================================================
                # If there is no mask and no payload we are done.
                #==============================================================
                if self.length <= 0:
                    try:
                        self._handle_packet()
                    finally:
                        self.state = HEADERB1
                        self.data = bytearray()
                #==============================================================
                # We have no mask and some payload.
                #==============================================================
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD
        elif length == 126:
            self.lengtharray = bytearray()
            self.state = LENGTHSHORT
        elif length == 127:
            self.lengtharray == bytearray()
            self.state = LENGTHLONG
    
    def _length_short(self, byte):
        self.lengtharray.append(byte)
        
        if len(self.lengtharray) > 2:
            raise Exception('error: short length exceeded allowable size')
        
        if len(self.lengtharray) == 2:
            self.length = struct.unpack_from('!H', self.lengtharray)[0]
            
            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                #==============================================================
                # If there is no mask and no payload we are done.
                #==============================================================
                if self.length <= 0:
                    try:
                        self._handle_packet()
                    finally:
                        self.state = HEADERB1
                        self.data = bytearray()
                #==============================================================
                # We have no mask and some payload.
                #==============================================================
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD
    
    def _length_long(self, byte):
        self.lengtharray.append(byte)
        
        if len(self.lengtharray) > 8:
            raise Exception('error: long length exceeded allowable size')
        
        if len(self.lengtharray) == 8:
            self.length = struct.unpack_from('!Q', self.lengtharray)[0]
            
            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                #==============================================================
                # If there is no mask and no payload we are done.
                #==============================================================
                if self.length <= 0:
                    try:
                        self._handle_packet()
                    finally:
                        self.state = HEADERB1
                        self.data = bytearray()
                #==============================================================
                # We have no mask and some payload.
                #==============================================================
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD
    
    def _mask(self, byte):
        self.maskarray.append(byte)
        
        if len(self.maskarray) > 4:
            raise Exception('error: mask exceeded allowable size')
        
        if len(self.maskarray) == 4:
            #==================================================================
            # If there is no mask and no payload we are done.
            #==================================================================
            if self.length <= 0:
                try:
                    self._handle_packet()
                finally:
                    self.state = HEADERB1
                    self.data = bytearray()
            #==================================================================
            # We have no mask and some payload.
            #==================================================================
            else:
                self.data = bytearray()
                self.state = PAYLOAD
    
    def _parse_message(self, byte):
        #======================================================================
        # Read in the header.
        #======================================================================
        if self.state == HEADERB1:
            self._header_b1(byte)
        elif self.state == HEADERB2:
            self._header_b2(byte)
        elif self.state == LENGTHSHORT:
            self._length_short(byte)
        elif self.state == LENGTHLONG:
            self._length_long(byte)
        elif self.state == MASK:
            self._mask(byte)
        elif self.state == PAYLOAD:
            self._payload(byte)
    
    def _payload(self, byte):
        if self.hasmask is True:
            self.data.append(byte ^ self.maskarray[self.index % 4])
        else:
            self.data.append(byte)
        
        #======================================================================
        # If length exceeds allowable size then we except and remove
        # the connection.
        #======================================================================
        if len(self.data) >= self.maxpayload:
            raise Exception('error: payload exceeded allowable size')
        
        #======================================================================
        # Check if we have processed length bytes. If so we are done.
        #======================================================================
        if (self.index + 1) == self.length:
            try:
                self._handle_packet()
            finally:
                self.state = HEADERB1
                self.data = bytearray()
        else:
            self.index += 1
    
    def _send_buffer(self, buffer, sendall=False):
        size = len(buffer)
        tosend = size
        already_sent = 0
        
        while tosend > 0:
            try:
                #==============================================================
                # We should be able to send bytearray.
                #==============================================================
                sent = self.sock.send(buffer[already_sent:])
                
                if sent == 0:
                    raise RuntimeError('error: socket connection broken')
                
                already_sent += sent
                tosend -= sent
            except socket.error as e:
                #==============================================================
                # If we have full buffers then wait for them to drain
                # and try again.
                #==============================================================
                if e.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
                    if sendall:
                        continue;
                    return buffer[already_sent:]
                else:
                    raise e
        
        return None
    
    def _send_message(self, fin, opcode, data):
        payload = bytearray();
        
        b1 = 0
        b2 = 0
        
        if fin is False:
            b1 |= 0x80
        
        b1 |= opcode
        
        if _check_unicode(data):
            data = data.encode('utf-8')
        
        length = len(data)
        payload.append(b1)
        
        if length <= 255:
            b2 |= length
            payload.append(b2)
        elif length >= 126 and length <= 65535:
            b2 |= 126
            payload.append(b2)
            payload.extend(strunct.pack('!H', length))
        else:
            b2 |= 127
            payload.append(b2)
            payload.extend(struct.pack('!Q', length))
        
        if length > 0:
            payload.extend(data)
        
        self.sendq.append((opcode, payload))
    
    def close(self, status=1000, reason=u''):
        #======================================================================
        # Send close frame to the client. The underlying socket is only closed
        # when the client acknowledges the close frame.
        #
        # status is the closing identifier.
        # reason is the reason for the close.
        #======================================================================
        try:
            if self.closed is False:
                close_msg = bytearray()
                close_msg.extend(struct.pack('!H', status))
                
                if _check_unicode(reason):
                    close_msg.extend(reason.encode('utf-8'))
                else:
                    close_msg.extend(reason)
                
                self._send_message(False, CLOSE, close_msg)
                
                while self.sendq:
                    opcode, payload = self.sendq.popleft()
                    remaining = self._send_buffer(payload)
                    
                    if remaining is not None:
                        self.sendq.appendleft((opcode, remaining))
                        break
                    else:
                        if opcode == CLOSE:
                            raise Exception('info: received client close')
        except Exception as ex:
            sys.stderr.write('%s\n' % str(ex))    
        finally:
            self.closed = True
        
        try:
            self.sock.close()
        except Exception as ex:
            sys.stderr.write('%s\n' % str(ex))    
        
        sys.stdout.write('Client disconnected. Resource #%s\n' % self.fileno)
        
        #======================================================================
        # If we have a successful websocket connection.
        #======================================================================
        if self.handshaked:
            self.handle_close()
    
    def handle_close(self):
        pass
    
    def handle_connected(self):
        pass
    
    def handle_message(self):
        pass
    
    def send_message(self, data):
        #======================================================================
        # Send websocket data frame to the client.
        #
        # If data is a unicode object then the frame is sent as TEXT.
        # If the data is a bytearray object then the frame is sent as BINARY
        #======================================================================
        opcode = BINARY
        
        if _check_unicode(data):
            opcode = TEXT
        
        self._send_message(False, opcode, data)
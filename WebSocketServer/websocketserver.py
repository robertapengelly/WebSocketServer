#-------------------------------------------------------------------------------------
#
#   Copyright 2018 Robert Pengelly.
#
#   This file is part of Websockserver.
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

from    .websocket      import  *
from    select          import  select

import  os
import  re
import  socket
import  sys

class WebSocketServer(object):
    def __init__(self, host, port, ssl_context=None, websocketclass=WebSocket):
        try:
            self.master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.master.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.master.bind((host, port))
            self.master.listen(5)
            sys.stdout.write('Server started\nListening on: %s:%s\nMaster socket: Resource #%s\n'
                % (host, port, self.master.fileno()))
        except Exception as ex:
            self.master.close()
            sys.stderr.write('%s\n' % str(ex))
            sys.exit(2)
        
        self.ssl_context = ssl_context
        self.socks = {}
        self.listeners = [self.master]
        
        match = re.compile('(.*):(.*)')
        match = match.search(websocketclass)
        
        if match is not None and len(match.groups()) == 2:
            #print match.group(1)
            try:
                module_dir, module_file = os.path.split(match.group(1))
                sys.path.append(module_dir)
                
                module_name, module_ext = os.path.splitext(module_file)
                mod = __import__(module_name, globals(), locals(), match.group(2))
                
                self.websocketclass = getattr(mod, match.group(2))
            except Exception as ex:
                sys.stderr.write('%s\n' % str(ex))
                self.websocketclass = WebSocket
        else:
            self.websocketclass = WebSocket
    
    def _construct_websocket(self, sock, address):
        return self.websocketclass(self, sock, address)
    
    def _failed(self, socks):
        for fileno in socks:
            if fileno == self.master:
                self.close();
                sys.stderr.write('error: master socket failed\n')
                sys.exit(2)
            
            if fileno not in self.socks:
                continue
            
            sock = self.sockets[fileno]
            sock.close()
            
            del self.socks[fileno]
            self.listeners.remove(fileno)
    
    def _ready(self, socks):
        for fileno in socks:
            if fileno == self.master:
                sock = None
                
                try:
                    sock, address = self.master.accept();
                    
                    if self.ssl_context is not None:
                        sock = self.ssl_context.wrap_socket(sock, server_side=True)
                    
                    sock.setblocking(0)
                    fileno = sock.fileno()
                    
                    self.socks[fileno] = self._construct_websocket(sock, address)
                    self.listeners.append(fileno)
                    
                    sys.stdout.write('Client connected. Resource #%s\n' % fileno)
                except Exception as ex:
                    sys.stderr.write('%s\n' % str(ex))
                    if sock is not None:
                        sock.close()
            else:
                if fileno not in self.socks:
                    continue
                
                sock = self.socks[fileno]
                
                try:
                    sock._handle_data()
                except Exception as ex:
                    sys.stderr.write('%s\n' % str(ex))
                    sock.close()
                    
                    del self.socks[fileno]
                    self.listeners.remove(fileno)
    
    def _run(self):
        writers = []
        
        for fileno in self.listeners:
            if fileno == self.master:
                continue
            
            sock = self.socks[fileno]
            
            if sock.sendq:
                writers.append(fileno)
        
        ready, writers, failed = select(self.listeners, writers, self.listeners)
        
        self._writers(writers)
        self._ready(ready)
        self._failed(failed)
    
    def _write(self, fileno, sock):
        try:
            while sock.sendq:
                opcode, payload = sock.sendq.popleft()
                remaining = sock._send_buffer(payload)
                
                if remaining is not None:
                    sock.sendq.appendleft((opcode, remaining))
                    break
                else:
                    if opcode == CLOSE:
                        raise Exception('info: received client close')
        except Exception as ex:
            sys.stderr.write('%s\n' % str(ex))
            sock.close()
            
            del self.socks[fileno]
            self.listeners.remove(fileno)
    
    def _writers(self, socks):
        for fileno in socks:
            sock = self.socks[fileno]
            self._write(fileno, sock)
    
    def close(self):
        self.master.close()
        
        for desc, sock in self.socks.items():
            sock.close()
    
    def run(self):
        while True:
            self._run()
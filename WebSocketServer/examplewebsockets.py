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

from    .websocket  import  *

class SimpleEchoWebSocket(WebSocket):
    def handle_close(self):
        print ('%s disconnected' % str(self.address))
    
    def handle_connected(self):
        print ('%s connected' % str(self.address))
    
    def handle_message(self):
        self.send_message(self.data)
        print (self.data)

clients = []

class SimpleChatWebSocket(WebSocket):
    def handle_close(self):
        clients.remove(self)
        print ('Client %s closed.' % str(self.address))
        
        for client in clients:
            client.send_message(u'%s - disconnected' % self.address[0])
    
    def handle_connected(self):
        clients.append(self)
        print ('Client %s connected.' % str(self.address))
        
        for client in clients:
            client.send_message(u'%s - connected' % self.address[0])
    
    def handle_message(self):
        for client in clients:
            if client != self:
                client.send_message(u'%s - %s' % (self.address[0], self.data))
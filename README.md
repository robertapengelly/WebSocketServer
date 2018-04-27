## A Simple Websocket Server written in Python

- RFC 6455 (All latest browsers)
- TLS/SSL out of the box
- Passes Autobahns Websocket Testsuite
- Support for Python 2 and 3

#### Installation

You can install WebSocketServer by downloading the repsoitory and running the following command...

sudo python setup.py install

#### Echo Server Example
`````python
from WebSocketServer import WebSocket

class SimpleEcho(WebSocket):

    def handle_message(self):
        # echo message back to client
        self.send_message(self.data)

    def handle_connected(self):
        print(self.address, 'connected')

    def handle_close(self):
        print(self.address, 'closed')
`````

Run using the following command...

    python WebSocketServer --host host --port port --file file --socket socketclass
    (e.g. python WebSocketServer --host 127.0.0.1 --port 8443 --file /home/user/echosocket.py --socket SimpleEcho)

#### Chat Server Example
`````python
from WebSocketServer import WebSocket

clients = []

class SimpleChat(WebSocket):

    def handle_message(self):
        for client in clients:
            if client != self:
                client.send_message(self.address[0] + u' - ' + self.data)

    def handle_connected(self):
        print(self.address, 'connected')
        for client in clients:
            client.send_message(self.address[0] + u' - connected')
        clients.append(self)

    def handle_close(self):
        clients.remove(self)
        print(self.address, 'closed')
        for client in clients:
            client.send_message(self.address[0] + u' - disconnected')
`````

Run using the following command...

    python WebSocketServer --host host --port port --file file --socket socketclass
    (e.g. python WebSocketServer --host 127.0.0.1 --port 8443 --file /home/user/chatsocket.py --socket SimpleChat)

#### Want to get up and running faster?

There is an example which provides a simple echo and chat server

Echo Server

    python WebSocketServer --host 0.0.0.0 --port 8443 --file examplewebsockets.py --socket SimpleEchoWebSocket

Chat Server

    python WebSocketServer --host 0.0.0.0 --port 8443 --file examplewebsockets.py --socket SimpleChatWebSocket

#### TLS/SSL

If you have ssl configured on your server you can use it by running the following command...

    python SimpleExampleServer.py --cert certfile --pkey pkeyfile --ssldir ssldir
    (e.g. python SimpleExampleServer.py --cert cert.perm --pkey privkey.pem --ssldir /etc/letsencrypt/live/your_domain)

Note: The --ssldir is optional as you can include the full paths to the cert and key, the --ssldir was included to eliminate the need to type the directory twice.

#### For the Programmers

handle_connected: called when handshake is complete
 - self.address: TCP address port tuple of the endpoint

handle_close: called when the endpoint is closed or there is an error
 - self.address: TCP address port tuple of the endpoint

handle_message: gets called when there is an incoming message from the client endpoint
 - self.address: TCP address port tuple of the endpoint
 - self.opcode: the WebSocket frame type (STREAM, TEXT, BINARY)
 - self.data: bytearray (BINARY frame) or unicode string payload (TEXT frame)  
 - self.request: HTTP details from the WebSocket handshake (refer to BaseHTTPRequestHandler)

send_message: send some text or binary data to the client endpoint
 - sending data as a unicode object will send a TEXT frame
 - sending data as a bytearray object will send a BINARY frame

sendClose: send close frame to endpoint

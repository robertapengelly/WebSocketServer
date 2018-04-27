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

from    .compat             import  compat_get_terminal_size, compat_kwargs
from    .utils              import  preferredencoding
from    .websocketserver    import  *

from    os.path     import  join

import  optparser
import  re
import  signal
import  ssl
import  sys

__version__ = '2018.04.25'

def parse_opts(override=None):

    def _format_option_string(option):
        opts = []
        
        if option._short_opts:
            opts.append(option._short_opts[0])
        
        if option._long_opts:
            opts.append(option._long_opts[0])
        
        if len(opts) > 1:
            opts.insert(1, ', ')
        
        if option.takes_value():
            opt = (option.metavar if option.metavar or option.default == '' else option.default)
            opts.append(' %s' % opt)
        
        return ''.join(opts)
    
    #==============================================================
    # No need to wrap help messages if we're on a wide console.
    #==============================================================
    columns = compat_get_terminal_size().columns
    max_width = columns if columns else 80
    max_help_position = 80
    
    fmt = optparser.IndentedHelpFormatter(width=max_width,
        max_help_position=max_help_position)
    fmt.format_option_strings = _format_option_string
    
    kw = {
        'version': __version__,
        'formatter': fmt,
        'conflict_handler': 'resolve',
    }
    
    parser = optparser.OptionParser(**compat_kwargs(kw))
    parser.add_option("--host", default='0.0.0.0', type='string',
        action="store", dest="host", help="host (e.g 127.0.0.1, localhost)")
    parser.add_option("--port", default=8000, type='int',
        action="store", dest="port", help="port (8000)")
    parser.add_option("--ssldir", default='', type='string',
        action="store", dest="ssldir", help="ssl directory (/etc/letsencrypt/live/your_domain)")
    parser.add_option("--cert", default='', type='string',
        action="store", dest="cert", help="cert (cert.pem)")
    parser.add_option("--pkey", default='', type='string',
        action="store", dest="pkey", help="pkey (privkey.pem)")
    parser.add_option("--ver", default=ssl.PROTOCOL_TLSv1, type=int,
        action="store", dest="ver", help="ssl version")
    parser.add_option("--file", default='', type='string',
        action="store", dest="file",
        help="WebSocket Class File (e.g examplewebsockets)")
    parser.add_option("--socket", default='WebSocket', type='string',
        action="store", dest="socket",
        help="WebSocket Class (e.g SimpleEchoWebSocket, SimpleChatWebSocket)")
    
    if override is not None:
        opts, args = parser.parse_args(override)
    else:
        def compat_conf(conf):
            if sys.version_info < (3,):
                return [a.decode(preferredencoding(), 'replace') for a in conf]
            return conf
        
        command_line_conf = compat_conf(sys.argv[1:])
        opts, args = parser.parse_args(command_line_conf)
    
    return parser, opts, args

def main(argv=None):
    (parser, opts, args) = parse_opts(argv)
    
    if len(args) > 0:
        #==========================================================
        # Lets get any arguments passed without --.
        #
        # We'll assume that if an argument doesn't contain
        # an equals then the next argument is the value.
        #==========================================================
        nargs = []
        
        #==========================================================
        # We'll do a while loop as we'll be removing arguments
        # along the way.
        #==========================================================
        while len(args) > 0:
            arg = args[0];
            del args[0]
            
            #======================================================
            # Now that we have the first argument, lets check
            # if it contains an equals, if it doesn't we'll
            # add one folowed by the next argument.
            #======================================================
            if arg.find('=') == -1 and len(args) > 0:
                arg += '=%s' % args[0]
                del args[0]
            
            #======================================================
            # Finally lets append the new argument to our nargs,
            # don't forget to prepend --.
            #======================================================
            nargs.append('--%s' % arg)
        
        #==========================================================
        # Now that we have our new arguments lets parse them
        # so that they take effect.
        #==========================================================
        (parser, opts, args) = parse_opts(nargs)
    
    #==============================================================
    # Before we go further we need to check that our host
    # is a valid one. We had to give it a type string as we
    # are handling multiple decimal points, lets make sure
    # we don't have something else.
    #==============================================================
    #if opts.host != 'localhost' and not re.match('[\d]{1,3}\\.[\d]{1,3}\\.[\d]{1,3}\\.[\d]{1,3}', opts.host):
    if opts.host != 'localhost' and not re.match('^(([\d]{1,3})\\.){3}([\d]{1,3})', opts.host):
        sys.stderr.write('error: option --host: invalid host value: %s\n' % opts.host)
        parser.print_help()
        sys.exit(2)
    
    #==============================================================
    # Finally lets configure and start the main socket.
    #==============================================================
    ssl_context = None
    
    if opts.cert != '' and opts.pkey != '':
        if opts.ssldir != '':
            opts.cert = join(opts.ssldir, opts.cert)
            opts.pkey = join(opts.ssldir, opts.pkey)
        
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            ssl_context.load_cert_chain(opts.cert, opts.pkey)
        except Exception as ex:
            sys.stderr.write('%s\n' % str(ex))
            sys.exit(2)
    
    server = WebSocketServer(('0.0.0.0' if opts.host == '' else opts.host),
        opts.port, ssl_context, ':'.join([opts.file, opts.socket]))
    
    def close_sig_handler(signal, frame):
        server.close()
        sys.exit()
    
    signal.signal(signal.SIGINT, close_sig_handler)
    server.run()

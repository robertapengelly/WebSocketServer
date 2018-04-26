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

import  optparse
import  sys

class OptionParser(optparse.OptionParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help();
        sys.exit(2)

class IndentedHelpFormatter(optparse.IndentedHelpFormatter):
    def __init__(self, indent_increment=2, max_help_position=24, width=None, short_first=1):
        optparse.IndentedHelpFormatter.__init__(self, indent_increment, max_help_position, width, short_first)
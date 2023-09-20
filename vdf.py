#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
vdf.py - reading and manipulating Steam text .vdf Files
http://steamcommunity.com/groups/familysharing/discussions/0/540736965953254153/
"""

__copyright__ = "© 2014-2017 by Thomas Schmidt (PsyBlade)"
__license__ = "GPL-3.0-or-later"

#    This file is part of sfs-select.
#
#    sfs-select is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    sfs-select is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with sfs-select.  If not, see <https://www.gnu.org/licenses/>.


import shlex
from collections import defaultdict

class VdfStr(str):
    def __new__(cls, value, sourcefile, line):
        obj = str.__new__(cls, value)
        obj.start = line
        obj.end = line + 1
        obj.sourcefile = sourcefile
        return obj

    def getraw(self):
        return self.sourcefile.raw[self.start:self.end]


class VdfSect(defaultdict):
    def __init__(self, sourcefile, start):
        super(VdfSect, self).__init__(defaultdict, [])
        self.start = start
        self.end = start + 1
        self.sourcefile = sourcefile

    def getraw(self):
        return self.sourcefile.raw[self.start:self.end]

    def clear(self):
        self.sourcefile.dellines(self.start + 2, self.end - 1)

    def append(self, lines):
        self.sourcefile.inslines(self.end - 1, lines)

class VdfFile(object):
    def __init__(self, sourcefile):
        self.sourcefile = sourcefile
        self.raw = []
        self.inslist = []
        self.dellist = []
        self.data = {}
        self.encoding = "utf-8"
        try:
            self.parse()
        except UnicodeDecodeError:
            self.encoding = "cp1252"
            self.parse()

    def parse(self):
        self.raw = []
        self.inslist = []
        self.dellist = []
        stack = []
        config = VdfSect(self.raw, 0)
        current = config
        with open(self.sourcefile, encoding=self.encoding) as handle:
            for line in handle:
                self.raw.append(line)
                self.inslist.append([])
                self.dellist.append(False)
            handle.seek(0)
            lexer = shlex.shlex(handle, posix=True)
            while True:
                name = lexer.get_token()
                num = lexer.lineno-1
                if name == None:
                    break
                if name == '}':
                    current, name = stack.pop()
                    current[name].end = num+1
                    #print(num, "end", name)
                else:
                    value = lexer.get_token()
                    if value == '{':
                        #print(num-1, "start", name)
                        new = VdfSect(self, num-1)
                        current[name] = new
                        stack.append((current, name))
                        current = new
                    else:
                        #print("\t", num, name, value)
                        current[name] = VdfStr(value, self, num)
        config.end = len(self.raw) - 1
        self.data = config

    def inslines(self, line, content):
        self.inslist[line].extend(content)

    def dellines(self, start, end):
        for line in range(start, end):
            self.dellist[line] = True

    def getraw(self):
        return self.raw

    def compilenewfile(self, newfile):
        with open(newfile, "w", encoding=self.encoding) as new:
            for orgline, delete, insert in zip(self.raw, self.dellist, self.inslist):
                for insline in insert:
                    new.write(insline)
                if not delete:
                    new.write(orgline)

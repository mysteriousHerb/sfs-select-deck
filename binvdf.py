#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
binvdf.py - reading of Steam binary .vdf files
http://steamcommunity.com/groups/familysharing/discussions/0/540736965953254153/
"""

__copyright__ = "© 2015-2017 by Thomas Schmidt (PsyBlade)"
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


import struct
import base64

s_int = struct.Struct("I")
s_long = struct.Struct("Q")

def readint():
    return s_int.unpack(infile.read(4))[0]

def readlong():
    return s_long.unpack(infile.read(8))[0]

def readstr():
    res = []
    while True:
        p = infile.peek()
        length = p.find(b'\x00')
        if length > -1:
            res.append(infile.read(length+1))
            res = b''.join(res)[:-1]
            try:
                return res.decode("utf8")
            except Exception:
                return res.decode("latin1")
        res.append(infile.read(len(p)))

def readdict():
    res = {}
    while True:
        dtype = infile.read(1)
        if dtype == b'\x08':
            break
        name = readstr()
        if dtype == b'\x00':
            value = readdict()
        elif dtype == b'\x01':
            value = readstr()
        elif dtype == b'\x02':
            value = readint()
        elif dtype == b'\x07':
            value = readlong()
        else:
            print("unknown\t", dtype, name)
            print(infile.read(50))
            raise Exception
        res[name] = value
    return res

def readapp():
    app = {}
    app["unknown1"] = readint()
    app["last_updated"] = readint()
    app["access_token"] = readlong()
    app["sha1"] = base64.b16encode(infile.read(20))
    app["change"] = hex(readint())
    app.update(readdict())
    return app

def parsepkginfo(filename, limit=None):
    global infile
    with open(filename, "rb") as infile:
        res = {}
        res["version"] = hex(readint())
        res["universe"] = hex(readint())
        res["pkgs"] = {}
        while True:
            pkgid = readint()
            if pkgid == 0xffffffff:
                break
            pkg = {}
            pkg["sha1"] = base64.b16encode(infile.read(20))
            pkg["change"] = hex(readint())
            pkg.update(readdict())
            if not limit or pkgid in limit:
                res["pkgs"][pkgid] = pkg
    return res

def parseappinfo(filename, limit=None):
    global infile
    with open(filename, "rb") as infile:
        res = {}
        res["version"] = hex(readint())
        res["universe"] = hex(readint())
        res["apps"] = {}
        while True:
            appid = readint()
            if appid == 0x0:
                break
            app = {}
            app["data_size"] = readint()
            if not limit or appid in limit:
                app["data_pos"] = infile.tell()
                app.update(readapp())
                res["apps"][appid] = app
                assert(infile.tell() == app["data_size"] + app["data_pos"])
            else:
                infile.seek(app["data_size"], 1)
    return res

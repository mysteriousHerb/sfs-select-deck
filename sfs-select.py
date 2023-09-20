#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sfs-select.py - Steam Family Sharing source selection
http://steamcommunity.com/groups/familysharing/discussions/0/540736965953254153/
"""

__copyright__ = "© 2014-2019 by Thomas Schmidt (PsyBlade)"
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


import time
import os
import argparse
import json
import sys
import psutil

import vdf
import binvdf
import gui

from PyQt5 import QtCore, QtWidgets
from collections import defaultdict

class sfs_select(object):
    settings_file = "sfs-settings.json"

    def __init__(self):
        self.read_settings() 

    def read_settings(self):
        newfile = False
        try:
            with open(self.settings_file, encoding="utf-8") as handle:
                self.settings = json.load(handle)
        except IOError:
            self.settings = {}
            newfile = True
        self.settings.setdefault("steampath", os.path.join("..", ".."))
        self.settings.setdefault("order", [])
        self.settings.setdefault("namecache", {})
        self.settings.setdefault("autoquit", False)
        self.settings.setdefault("autostart", False)
        self.settings.setdefault("autorestart", False)
        self.settings["namecache"].setdefault("time", 0)
        self.settings["namecache"].setdefault("content", {})
        self.settings["namecache"].setdefault("fallback", {})

        if sys.platform == "win32":
            self.settings.setdefault("steampath2", self.settings["steampath"])
            self.steam_exe = os.path.join(self.settings["steampath"], "Steam.exe")
            self.steam_name = "Steam.exe"
        else:
            self.settings.setdefault("steampath2", os.path.join(self.settings["steampath"], "steam"))
            self.steam_exe = os.path.join(self.settings["steampath"], "steam.sh")
            self.steam_name = "steam"

        self.file_config = os.path.join(self.settings["steampath2"], "config", "config.vdf")
        self.file_disabled = "sfs-disabled.vdf"
        if newfile:
            self.write_settings()

    def write_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as handle:
            json.dump(self.settings, handle, sort_keys=True, indent=4, separators=(',', ': '))

    def read_shares(self):
        if not os.path.isfile(self.file_disabled):
            with open(self.file_disabled, "w", encoding="utf-8") as handle:
                handle.write('"InstallConfigStore"\n{\n')
                handle.write('\t"AuthorizedDevice"\n\t{\n\t}\n')
                handle.write('}\n')
        self.share = {}
        self.vdf_config = vdf.VdfFile(self.file_config)
        self.vdf_disabled = vdf.VdfFile(self.file_disabled)
        namelist = self.settings["namecache"]["content"]
        for idnum, share in sorted(list(self.vdf_config.data['InstallConfigStore']['AuthorizedDevice'].items()), key=lambda x: x[1].start):
            self.share[idnum] = sfs_share(share, True, idnum, namelist.get(idnum, "Unknown Lender"))
            if idnum not in self.settings["order"]:
                self.settings["order"].append(idnum)
        for idnum, share in sorted(list(self.vdf_disabled.data["InstallConfigStore"]["AuthorizedDevice"].items()), key=lambda x: x[1].start):
            if idnum not in self.share:
                self.share[idnum] = sfs_share(share, False, idnum, namelist.get(idnum, "Unknown Lender"))
                if idnum not in self.settings["order"]:
                    self.settings["order"].append(idnum)
        for share in self.settings["order"][:]:
            if share not in self.share:
                self.settings["order"].remove(share)

    def write_shares(self):
        disabled = self.vdf_disabled.data["InstallConfigStore"]["AuthorizedDevice"]
        enabled = self.vdf_config.data["InstallConfigStore"]["AuthorizedDevice"]
        disabled.clear()
        enabled.clear()
        for uid in self.settings["order"]:
            share = self.share[uid]
            if share.enabled:
                enabled.append(share.vdf_sect.getraw())
            else:
                disabled.append(share.vdf_sect.getraw())
        self.vdf_disabled.compilenewfile(self.file_disabled + ".new")
        self.vdf_config.compilenewfile(self.file_config + ".new")
        os.remove(self.file_disabled)
        os.rename(self.file_disabled + ".new", self.file_disabled)
        os.remove(self.file_config)
        os.rename(self.file_config + ".new", self.file_config)

    def print_shares(self):
        print("Shares:")
        form = "  {:<4} {:>3}   {:<16} {:>9}   {}"
        print(form.format("stat", "pri", "lender name", "lender ID", "last use"))
        for num, uid in enumerate(self.settings["order"], 1):
            share = self.share[uid]
            share.printshare(num)

    def gathernames(self):
        namecache = self.settings["namecache"]["content"]
        fallback = self.settings["namecache"]["fallback"]
        if self.settings["namecache"]["time"] + 360 < time.time():
            namecache.clear()
            self.settings["namecache"]["time"] = time.time()
        namelist = namecache.copy()
        for idnum in self.share:
            namelist.setdefault(idnum, "Unknown Lender")
        for idnum, name in self.vdf_config.data['InstallConfigStore']['AuthorizedLender'].items():
            try:
                if namelist[idnum] == "Unknown Lender":
                    namelist[idnum] = name
                    namecache[idnum] = name
            except LookupError:
                pass
        if "Unknown Lender" in namelist.values():
            userfiles = []
            for root, _, files in os.walk(os.path.join(self.settings["steampath2"], "userdata")):
                if "localconfig.vdf" in files:
                    fname = os.path.join(root, "localconfig.vdf")
                    userfiles.append((os.path.getmtime(fname), fname))
            userfiles.sort()
        while "Unknown Lender" in namelist.values() and userfiles:
            try:
                lcfg = vdf.VdfFile(userfiles.pop()[1])
                for idnum, data in lcfg.data["UserLocalConfigStore"]["friends"].items():
                    try:
                        if namelist[idnum] == "Unknown Lender":
                            namelist[idnum] = str(data["name"])
                            namecache[idnum] = str(data["name"])
                    except (LookupError, TypeError):
                        pass
            except (UnicodeDecodeError, KeyError):
                pass
        self.idlist = {}
        for uid, _ in self.share.items():
            name = namelist[uid]
            if name == "Unknown Lender":
                self.share[uid].namefallback = True
                try:
                    name = fallback[uid]
                    namelist[uid] = name
                except LookupError:
                    pass
            self.idlist[name] = uid
            self.share[uid].name = name
        self.settings["namecache"]["fallback"] = namelist

    def getid(self, shareid):
        if shareid not in self.share:
            shareid = self.idlist[shareid]
        return shareid

    def getallids(self, idlists):
        if idlists:
            for idlist in idlists:
                for shareid in idlist:
                    try:
                        yield self.getid(shareid)
                    except LookupError:
                        print("Error: can't find", shareid)

    def do_upgrade(self):
        if 'AuthorizedLender' in self.vdf_disabled.data['InstallConfigStore']:
            print("upgrading data format to 0.0.3")
            for lender in self.vdf_disabled.data['InstallConfigStore']['AuthorizedLender'].items():
                self.vdf_config.inslines(self.vdf_config.data['InstallConfigStore']['AuthorizedLender'].end-1, lender[1].getraw())
            self.vdf_disabled.dellines(self.vdf_disabled.data['InstallConfigStore']['AuthorizedLender'].start, self.vdf_disabled.data['InstallConfigStore']['AuthorizedLender'].end)
            self.write_shares()
            self.read_shares()

    def gather_source(self):
        self.pkg_to_uids = defaultdict(set)
        self.app_to_pkg = defaultdict(set)
        for uid in self.share:
            try:
                lcfg = vdf.VdfFile(os.path.join(self.settings["steampath2"], "userdata", uid, "config", "localconfig.vdf"))
                for sub in lcfg.data["UserLocalConfigStore"]["Licenses"]:
                    self.pkg_to_uids[int(sub)].add(uid)
            except Exception:
                pass
        pkginfo = binvdf.parsepkginfo(os.path.join(self.settings["steampath2"], "appcache", "packageinfo.vdf"))
        for pkg, data in pkginfo["pkgs"].items():
            if pkg in self.pkg_to_uids:
                try:
                    for app in data[str(pkg)]['appids'].values():
                        self.app_to_pkg[app].add(pkg)
                except Exception:
                    pass

    def locate_source(self, targetapps):
        targetapps = [int(item) for sublist in targetapps for item in sublist]
        self.gather_source()
        priolist = {uid: prio for prio, uid in enumerate(self.settings["order"], 1)}
        appinfo = binvdf.parseappinfo(os.path.join(self.settings["steampath2"], "appcache", "appinfo.vdf"), limit=targetapps)
        for app in targetapps:
            if len(targetapps) > 1:
                print()
            try:
                print("sources for app {} ({}):".format(app, appinfo["apps"][app]["appinfo"]["common"]["name"]))
                packages = sorted(self.app_to_pkg[app])
                if packages:
                    for package in packages:
                        print(" package {:>6}:".format(package))
                        sources = [(priolist[uid], uid) for uid in self.pkg_to_uids[package]]
                        for prio, uid in sorted(sources):
                            self.share[uid].printshare(prio, False)
                else:
                    print(" none")
            except KeyError:
                print("unknown app {}".format(app))

    def quit_steam(self):
        ret = False
        for proc in psutil.process_iter():
            try:
                if proc.name() == self.steam_name:
                    q = False
                    try:
                        q = psutil.Popen([self.steam_exe, "-shutdown"])
                        q.wait(10)
                        proc.wait(10)
                    except (psutil.TimeoutExpired, PermissionError, FileNotFoundError):
                        if q:
                            q.kill()
                        proc.kill()
                    ret = True
            except(PermissionError, psutil.AccessDenied):
                pass
        if ret:
            time.sleep(2)
        return ret

    def start_steam(self):
        try:
            psutil.Popen([self.steam_exe])
        except Exception:
            pass


class sfs_share(object):
    format = "  {:<4} {:>3}   {:<16} {:>9}   {}"

    def __init__(self, sect, enabled, uid, name):
        self.vdf_sect = sect
        self.enabled = enabled
        self.uid = uid
        self.name = name
        self.namefallback = False

    def printshare(self, num, printuse=True):
        if printuse:
            tuse = time.strftime("%c", time.localtime(float(self.vdf_sect.get('timeused', 0))))
        else:
            tuse = ""
        enabled = "on" if self.enabled else "off"
        print(self.format.format(enabled, num, self.name, self.uid, tuse))


class MainProgram(QtWidgets.QMainWindow, gui.Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainProgram, self).__init__(parent)
        self.sfs = sfs
        self.setupUi(self)
        self.tableWidget.setRowCount(len(self.sfs.share))
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(("status", "priority", "lender name", "lender ID", "last use"))
        self.tableWidget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.sortByColumn(1, QtCore.Qt.AscendingOrder)
        self.resetTable()

    def resetTable(self):
        self.tableWidget.clearContents()
        self.tableWidget.setSortingEnabled(False)
        self.tableWidget.blockSignals(True)

        for num, uid in enumerate(self.sfs.settings["order"]):
            share = self.sfs.share[uid]
            item = QtWidgets.QTableWidgetItem("enable")
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if share.enabled:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget.setItem(num, 0, item)
            item = QtWidgets.QTableWidgetItem()
            item.setData(QtCore.Qt.EditRole, int(num + 1))
            self.tableWidget.setItem(num, 1, item)
            self.tableWidget.openPersistentEditor(item)
            item = QtWidgets.QTableWidgetItem()
            item.setData(QtCore.Qt.EditRole, str(share.name))
            self.tableWidget.setItem(num, 2, item)
            if share.namefallback:
                self.tableWidget.openPersistentEditor(item)
            item = QtWidgets.QTableWidgetItem()
            item.setData(QtCore.Qt.EditRole, int(uid))
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.tableWidget.setItem(num, 3, item)
            item = QtWidgets.QTableWidgetItem()
            tuse = int(share.vdf_sect.get('timeused', 0))
            item.setData(QtCore.Qt.DisplayRole, QtCore.QDateTime.fromTime_t(tuse))
            self.tableWidget.setItem(num, 4, item)

        self.tableWidget.blockSignals(False)
        self.tableWidget.setSortingEnabled(True)
        self.tableWidget.resizeColumnsToContents()

    @QtCore.pyqtSlot(QtWidgets.QAbstractButton)
    def on_buttonBox_clicked(self, button):
        if self.buttonBox.buttonRole(button) == QtWidgets.QDialogButtonBox.AcceptRole:
            order = []
            for row in range(self.tableWidget.rowCount()):
                enabled = (self.tableWidget.item(row, 0).checkState() == QtCore.Qt.Checked)
                prio = self.tableWidget.item(row, 1).text()
                name = self.tableWidget.item(row, 2).text()
                uid = self.tableWidget.item(row, 3).text()
                self.sfs.share[uid].enabled = enabled
                order.append((prio, uid))
                self.sfs.settings["namecache"]["fallback"][uid] = name
            self.sfs.settings["order"] = [x[1] for x in sorted(order)]
            self.sfs.write_settings()
            self.sfs.write_shares()
            self.close()
        if self.buttonBox.buttonRole(button) == QtWidgets.QDialogButtonBox.RejectRole:
            self.close()
        if self.buttonBox.buttonRole(button) == QtWidgets.QDialogButtonBox.ResetRole:
            self.resetTable()

#    @QtCore.Slot(QtWidgets.QTableWidgetItem)
#    def on_tableWidget_itemChanged(self, item):
#        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list', action='store_true', help='show a textual list of all shares')
    parser.add_argument('-g', '--gui', action='store_true', help='show grapical user interface')
    enable = parser.add_argument_group('enable/disable shares')
    enable.add_argument('-e', '--enable', nargs='+', action='append', metavar='SHARE', help='shares to enable')
    enable.add_argument('-d', '--disable', nargs='+', action='append', metavar='SHARE', help='shares to disable')
    enableex = enable.add_mutually_exclusive_group()
    enableex.add_argument('-E', '--enable-others', action='store_true', help='enable all shares not explicitly disabled')
    enableex.add_argument('-D', '--disable-others', action='store_true', help='disable all shares not explicitly enabled')
    prio = parser.add_argument_group('change share priority')
    prio.add_argument('-H', '--high-priority', nargs='+', action='append', metavar='SHARE', help='shares to put on top of priority list')
    prio.add_argument('-L', '--low-priority', nargs='+', action='append', metavar='SHARE', help='shares to put on bottom of priority list')
    special = parser.add_argument_group("special features")
    specialex = special.add_mutually_exclusive_group()
    specialex.add_argument('-f', '--locate-source', nargs='+', action='append', metavar='APPID', help='show the sources of specific games')
    exp = parser.add_argument_group('experimental features')
    exp.add_argument('-Q', '--quit-steam', action='store_true', help='quit steam before starting sfs-select')
    exp.add_argument('-S', '--start-steam', action='store_true', help='start steam after sfs-select is done')
    exp.add_argument('-R', '--restart-steam', action='store_true', help='as above but only if it was running')
    exp.add_argument('-N', '--no-auto-steam', action='store_true', help='ignore autostart/quit settings in configfile')
    args = parser.parse_args()

    global gui
    mode_edit = args.enable or args.disable or args.enable_others or args.disable_others or args.high_priority or args.low_priority
    gui = args.gui
    if args.locate_source:
        if mode_edit or gui:
            print("ERROR: special featues are incomptible with other options")
            sys.exit(1)
    elif (not mode_edit) and (not args.list):
        gui = True
    if gui:
        mode_edit = True
        gui = QtWidgets.QApplication(sys.argv)
    global sfs
    sfs = sfs_select()
    quit_steam = args.quit_steam or (not args.no_auto_steam and sfs.settings["autoquit"])
    start_steam = args.start_steam or (not args.no_auto_steam and sfs.settings["autostart"])
    restart_steam = args.restart_steam or (not args.no_auto_steam and sfs.settings["autorestart"])
    while not os.path.isfile(sfs.steam_exe):
        if gui:
            selected = QtWidgets.QFileDialog.getExistingDirectory(None, "Please select Steam directory")
            if selected == "":
                sys.exit(1)
            sfs.settings["steampath"] = selected
            sfs.write_settings()
            sfs.read_settings()
        else:
            print("Can't find {}".format(sfs.steam_exe))
            print("You might need to edit {} to point to the steam directory".format(sfs.settings_file))
            print("or run the GUI for a selection dialog")
            sys.exit(1)
    if not os.path.isfile(sfs.file_config):
        for sdir in ["", "steam"]:
            sfs.settings["steampath2"] = os.path.join(sfs.settings["steampath"], sdir)
            sfs.write_settings()
            sfs.read_settings()
            if os.path.isfile(sfs.file_config):
                break
        else:
            print("Can't find {}".format(sfs.file_config))
            print("You might need to edit {} to point to the steam directory".format(sfs.settings_file))
            sys.exit(1)

    if mode_edit and quit_steam:
        quited_steam = sfs.quit_steam()
        start_steam = start_steam or (restart_steam and quited_steam)

    sfs.read_shares()
    sfs.do_upgrade()
    sfs.gathernames()
    sfs.write_settings()

    if mode_edit or gui:
        if args.enable_others or args.disable_others:
            for share in sfs.share.values():
                share.enabled = args.enable_others
        for shareid in sfs.getallids(args.enable):
            sfs.share[shareid].enabled = True
        for shareid in sfs.getallids(args.disable):
            sfs.share[shareid].enabled = False
        if args.high_priority or args.low_priority:
            done = set()
            first = []
            keep = []
            last = []
            for uid in sfs.getallids(args.high_priority):
                if uid not in done:
                    first.append(uid)
                    done.add(uid)
            for uid in sfs.getallids(args.low_priority):
                if uid not in done:
                    last.append(uid)
                    done.add(uid)
            for uid in sfs.settings["order"]:
                if uid not in done:
                    keep.append(uid)
            sfs.settings["order"] = first + keep + last
        if gui:
            show_gui()
        else:
            sfs.write_settings()
            sfs.write_shares()
            sfs.read_shares()
            sfs.print_shares()

    elif args.list:
        sfs.print_shares()

    elif args.locate_source:
        sfs.locate_source(args.locate_source)

    if start_steam:
        sfs.start_steam()


def show_gui():
    mainw = MainProgram()
    mainw.show()
    gui.exec_()

if __name__ == '__main__':
    main()

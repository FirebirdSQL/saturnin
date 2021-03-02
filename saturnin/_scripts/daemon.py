#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/daemon.py
# DESCRIPTION:    Script to start/stop the daemon process.
# CREATED:        9.11.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin script to start/stop the daemon process.


"""

from __future__ import annotations
import platform
import argparse
from pathlib import Path
from saturnin.lib.daemon import start_daemon

def main():
    """Starts or stops the daemon process.
    """
    parser = argparse.ArgumentParser('saturnin-daemon', description=main.__doc__)
    subs = parser.add_subparsers(title="Commands", dest='action', required=True)
    start_args = subs.add_parser('start', help="Starts daemon process")
    start_args.add_argument('pid_file', help="Path to PID file")
    start_args.add_argument('daemon', help="Path to daemon")
    start_args.add_argument('arguments', nargs=argparse.REMAINDER, help="Daemon arguments")

    stop_args = subs.add_parser('stop', help="Stops daemon process")
    stop_args.add_argument('pid', help="Daemon PID or path to PID file")

    args = parser.parse_args()

    if args.action == 'start':
        pid_file = Path(args.pid_file)
        pid_file.write_text('') # ensure it's writtable
        args.arguments.insert(0, args.daemon)
        pid = start_daemon(args.arguments)
        pid_file.write_text(str(pid))
    else: # stop
        try:
            pid = int(args.pid)
        except ValueError:
            pid = int(Path(args.pid).read_text())
        if platform.system() == 'Windows':
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.FreeConsole()
            kernel.AttachConsole(pid)
            kernel.SetConsoleCtrlHandler(None, 1)
            kernel.GenerateConsoleCtrlEvent(0, 0)
        else:  # Unix
            import os
            import signal
            os.kill(pid, signal.SIGINT)

if __name__ == '__main__':
    main()

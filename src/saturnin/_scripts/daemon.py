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
 # pylint: disable=C0415,W1514

"""Saturnin script to start/stop the daemon process.


"""

from __future__ import annotations
import platform
import argparse
from pathlib import Path
from saturnin.lib.daemon import start_daemon

def main():
    """Saturnin script to start or stop the daemon process.

    usage::

      saturnin-daemon [-h] {start,stop} ...

    optional arguments:
      -h, --help    show this help message and exit

    Commands:
      {start,stop}
        start       Starts daemon process
        stop        Stops daemon process

    start comand::

      saturnin-daemon start [-h] [-p PID_FILE] daemon ...

    positional arguments:
      daemon                Path to daemon
      arguments             Daemon arguments

    optional arguments:
      -h, --help            show this help message and exit
      -p PID_FILE, --pid-file PID_FILE
                            Path to PID file

    stop command::

      saturnin-daemon stop [-h] pid

    positional arguments:
      pid         Daemon PID or path to PID file

    optional arguments:
      -h, --help  show this help message and exit
    """
    parser = argparse.ArgumentParser(description="Starts or stops the daemon process.")
    subs = parser.add_subparsers(title="Commands", dest='action', required=True)
    start_args = subs.add_parser('start', help="Starts daemon process")
    start_args.add_argument('-p', '--pid-file', help="Path to PID file")
    start_args.add_argument('daemon', help="Path to daemon")
    start_args.add_argument('arguments', nargs=argparse.REMAINDER, help="Daemon arguments")

    stop_args = subs.add_parser('stop', help="Stops daemon process")
    stop_args.add_argument('pid', help="Daemon PID or path to PID file")

    args = parser.parse_args()
    try:
        if args.action == 'start':
            if args.pid_file:
                pid_file = Path(args.pid_file)
                pid_file.write_text('') # ensure it's writtable
            else:
                pid_file = None
            args.arguments.insert(0, args.daemon)
            pid = start_daemon(args.arguments)
            if not pid:
                parser.exit(1, "Daemon start operation failed")
            if pid_file:
                pid_file.write_text(str(pid))
            else:
                print('Daemon PID:', pid)
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
    except Exception: # pylint: disable=W0703
        parser.exit(1)

if __name__ == '__main__':
    main()

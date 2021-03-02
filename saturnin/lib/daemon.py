#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/daemon.py
# DESCRIPTION:    Daemon process management
# CREATED:        6.11.2020
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

"""Saturnin daemon process management


"""

from __future__ import annotations
from typing import Union
import platform
import subprocess
from pathlib import Path

def start_daemon(args: list) -> int:
    """Starts daemon process.

    Arguments:
        args: Arguments for `subprocess.Popen` (first item must be the daemon filename)

    Returns:
        PID for started daemon, or None if start failed.

    Note:
        Gracefull shutdown on Windows is tricky. To allow shutdown via SIGINT signal handler
        (note that SIGINT is not available on Windows, you have to use CTRL_C_EVENT),
        it's necessry to start new shell with new console in background (i.e. detached from
        console of this daemon starting script).
    """
    kwargs = {}
    if platform.system() == 'Windows':
        kwargs.update(shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:  # Unix
        kwargs.update(start_new_session=True)
    p = subprocess.Popen(args, **kwargs)
    return p.pid if p.poll() is None else None

def stop_daemon(pid: Union[int, str, Path]) -> None:
    """Stops the daemon process by invoking `saturnin-daemon` script.

    Arguments:
        pid: PID or text file name/Path where PID is stored.

    Raises:
        subprocess.CalledProcessError: When execution of `saturnin-daemon` failed.
        subprocess.TimeoutExpired: When `saturnin-daemon` does not finish in 5 seconds.

    Important:
        On Linux/Unix: Sends SIGINT signal to the daemon process.
        On Windows: Detaches from console, attaches itself to daemon console and sends
        control-C event to it.

    Note:
        Gracefull shutdown on Windows is tricky. It requires that the daemon process has
        a console, otherwise the CTRL_C_EVENT couldn't be delivered. This condition is met
        if daemon was started by :func:`start_daemon` or `saturnin-daemon` script.
    """
    if isinstance(pid, int):
        pid = str(pid)
    subprocess.run(['saturnin-daemon', 'stop', pid], check=True, timeout=5)

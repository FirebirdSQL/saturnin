# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/daemon.py
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

"""Saturnin daemon process management.

This module provides functions for starting and stopping Saturnin daemon
processes, handling platform-specific behaviors for process creation
and signal delivery (e.g., SIGINT on Unix, CTRL_C_EVENT on Windows).
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from saturnin.base import Error


def start_daemon(args: list[str]) -> int | None:
    """Starts daemon process.

    Arguments:
        args: Arguments for `subprocess.Popen` (first item must be the daemon filename)

    Returns:
        PID for started daemon, or None if start failed.

    Note:
        Graceful shutdown on Windows is tricky. To allow shutdown of the daemon process
        via a SIGINT-like mechanism (specifically, by sending a CTRL_C_EVENT, as SIGINT is
        not directly available), it is necessary to start a new shell with a new console in
        the background for the daemon process.
    """
    kwargs = {}
    if platform.system() == 'Windows':
        kwargs.update(shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE) # noqa: S604
    else:  # Unix
        kwargs.update(start_new_session=True)
    proc = subprocess.Popen(args, **kwargs) # noqa: S603
    return proc.pid if proc.poll() is None else None

def stop_daemon(pid: int | str | Path) -> None:
    """Stops the daemon process by invoking `saturnin-daemon` script.

    Arguments:
        pid: PID or text file name/Path where PID is stored.

    Raises:
        Error: If the `saturnin-daemon stop` command fails or times out. The original
               `subprocess.CalledProcessError` or `subprocess.TimeoutExpired` (if timeout
               of 10 seconds is reached) will be set as the `__cause__` of this `Error`.

    Important:
        On Linux/Unix: Sends SIGINT signal to the daemon process.
        On Windows: Detaches from console, attaches itself to daemon console and sends
        control-C event to it.

    Note:
        Graceful shutdown on Windows is tricky. It requires that the daemon process
        has a console; otherwise, the CTRL_C_EVENT cannot be delivered. This
        condition is met if the daemon was started by :func:`start_daemon` or
        the `saturnin-daemon` script directly.
    """
    try:
        subprocess.run(['saturnin-daemon', 'stop', str(pid)], check=True, timeout=10) # noqa: S603, S607
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Error("Daemon stop operation failed") from exc

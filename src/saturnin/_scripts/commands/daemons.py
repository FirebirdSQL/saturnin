# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/daemons.py
# DESCRIPTION:    Saturnin daemon commands
# CREATED:        16.02.2023
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
# Copyright (c) 2023 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Typer commands for managing Saturnin daemon processes.

This module provides CLI commands to list currently running Saturnin daemons,
show detailed information about a specific daemon process, and stop a running
daemon. Daemons are typically Saturnin recipes executed in `DAEMON` mode.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Final

import psutil
import typer
from rich import box
from rich.table import Table
from rich.text import Text
from saturnin.base import directory_scheme
from saturnin.component.recipe import RecipeInfo, recipe_registry
from saturnin.lib import daemon
from saturnin.lib.console import console

#: Typer command group for daemon management commands
app = typer.Typer(rich_markup_mode="rich", help="Saturnin daemons.")

NOT_AVAILABLE: Final[str] = '[dim]N/A[/dim]'

def get_first_line(text: str) -> str:
    """Returns the first non-empty line from the input string.

    Args:
        text: The string from which to extract the first line.

    Returns:
        The first line of the string, stripped of leading/trailing whitespace.
        Returns an empty string if the input is empty or only whitespace.
    """
    if not text:
        return ""
    return text.strip().split('\n', 1)[0]

def get_running_daemons() -> dict[int, str]:
    """Scans Saturnin's PID directory to identify running daemon processes.

    It checks each `.pid` file, reads the associated recipe name, and verifies
    if the process with that PID is still running using `psutil`. If a PID file
    points to a non-existent process, the stale PID file is removed.

    Returns:
        A dictionary where keys are process IDs (int) of running daemons,
        and values are the corresponding `RecipeInfo` objects. If a recipe
        associated with a running daemon is no longer installed, the value
        will be `None`.
    """
    result = {}
    for pid_file in directory_scheme.pids.glob('*.pid'):
        recipe_name = pid_file.read_text()
        pid = int(pid_file.stem)
        if psutil.pid_exists(pid):
            result[pid] = recipe_registry.get(recipe_name)
        else:
            pid_file.unlink() # Stale PID file
    return result

def pid_completer(ctx, args, incomplete) -> list[tuple[str, str]]: #noqa: ARG001
    """Click/Typer autocompletion function for running Saturnin daemon PIDs.

    Provides a list of (PID, recipe_name) tuples for autocompletion suggestions.

    Args:
        ctx: The Click/Typer context.
        args: The current command arguments.
        incomplete: The partially typed PID.

    Returns:
        A list of tuples, where each tuple contains the PID as a string
        and the associated recipe name (or an empty string if the recipe
        is unknown).
    """
    return [(str(pid), recipe.name if recipe else "")
            for pid, recipe in get_running_daemons().items()]

def format_size(size: int, decimals: int=2, *, binary_system: bool=True) -> str:
    """Formats a size in bytes into a human-readable string (e.g., KiB, MB, GB).

    Args:
        size: The size in bytes.
        decimals: The number of decimal places for the formatted size.
        binary_system: If True (default), uses binary prefixes (KiB, MiB).
                       If False, uses decimal prefixes (kB, MB).

    Returns:
        A string representing the human-readable size.
    """
    if binary_system:
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']
        largest_unit = 'YiB'
        step = 1024
    else:
        units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB']
        largest_unit = 'YB'
        step = 1000

    for unit in units:
        if size < step:
            return ('%.' + str(decimals) + 'f %s') % (size, unit)
        size /= step

    return ('%.' + str(decimals) + 'f %s') % (size, largest_unit)

@app.command()
def list_daemons() -> None:
    """Lists all currently running Saturnin daemon processes.

    Displays a table with the PID, status, associated recipe name,
    and a brief description of the recipe for each running daemon.
    If a daemon's recipe has been uninstalled, it's marked accordingly.
    """
    daemons = get_running_daemons()
    #
    if daemons:
        table = Table(title='Running Saturnin Daemons', box=box.ROUNDED)
        table.add_column('PID', style='cyan')
        table.add_column('Status', style='bold yellow')
        table.add_column('Recipe', style='green', overflow="fold")
        table.add_column('Description', style='white', overflow="fold")
        # Sort by PID for consistent listing
        sorted_daemons = sorted(daemons.items(), key=lambda item: item[0])
        recipe: RecipeInfo
        for pid, recipe in sorted_daemons:
            try:
                proc_status = psutil.Process(pid).status()
            except psutil.NoSuchProcess:
                proc_status = "Exited" # Should have been caught by get_running_daemons
            except psutil.AccessDenied:
                proc_status = "Access Denied"

            if recipe is None:
                table.add_row(str(pid), proc_status, '[warning]UNKNOWN RECIPE[/warning]',
                              "Recipe used by this daemon was uninstalled or is missing.")
            else:
                table.add_row(str(pid), proc_status, recipe.name,
                              get_first_line(recipe.description))
        console.print(table)
    else:
        console.print("No Saturnin daemons are currently running (or tracked by PID files).")

@app.command()
def show_daemon(
    pid: Annotated[int, typer.Argument(metavar='PID', autocompletion=pid_completer,
                                       help="The Process ID of the daemon to inspect")]
    ) -> None:
    """Displays detailed information about a running Saturnin daemon process.

    Information includes process status, creation time, resource usage (CPU, memory, I/O),
    command line, and associated user.
    """
    try:
        if not psutil.pid_exists(pid):
            console.print_error(f"Process with PID [item]{pid}[/] not found.")
            return
        proc = psutil.Process(pid)
        # Check if it's a Saturnin daemon (optional, but good for context)
        recipe_name = "Unknown"
        pid_file_path = directory_scheme.pids / f"{pid}.pid"
        if pid_file_path.exists():
            recipe_name = pid_file_path.read_text().strip()

        data = proc.as_dict(ad_value='N/A') # Use ad_value for graceful missing attrs
    except psutil.NoSuchProcess:
        console.print_error(f"Process with PID [item]{pid}[/] disappeared before details could be fetched.")
        return
    except psutil.AccessDenied:
        console.print_error(f"Access denied when trying to get details for PID [item]{pid}[/]. "
                            "Try running with higher privileges.")
        return
    except Exception as e:
        console.print_error(f"An error occurred while fetching details for PID [item]{pid}[/]: {e}")
        return

    created = datetime.datetime.fromtimestamp(data['create_time'])
    run_time = datetime.datetime.now() - created

    panel_title = f"  Details for Daemon PID [important]{pid}[/important]"
    if recipe_name != "Unknown":
        panel_title += f" (Recipe: [green]{recipe_name}[/green])"

    table = Table(title=panel_title, box=box.ROUNDED, show_header=False,
                  title_justify='left')
    table.add_column('', style='green', overflow='fold')
    table.add_column('', overflow='fold')
    #
    table.add_row('Status:', Text(str(data.get('status', NOT_AVAILABLE)), style='important'))
    table.add_row('Created:', created.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row('Run Time:', str(run_time).split('.')[0]) # Remove microseconds for brevity
    table.add_row('Name:', str(data.get('name', NOT_AVAILABLE)))
    table.add_row('Executable:', str(data.get('exe', NOT_AVAILABLE)))
    cmdline_str = ' '.join(data.get('cmdline', [])) if data.get('cmdline') else NOT_AVAILABLE
    table.add_row('Cmd. Line:', cmdline_str)
    table.add_row('CWD:', str(data.get('cwd', NOT_AVAILABLE)))
    table.add_row('User:', str(data.get('username', NOT_AVAILABLE)))

    table.add_row('# Threads:', str(data.get('num_threads', NOT_AVAILABLE)))
    if 'num_handles' in data: # Windows-specific
        table.add_row('# Handles:', str(data.get('num_handles', NOT_AVAILABLE)))
    if 'num_fds' in data: # POSIX-specific
        table.add_row('# File Descriptors:', str(data.get('num_fds', NOT_AVAILABLE)))

    children = data.get('children', [])
    if children: # psutil.Process.children() needs to be called explicitly usually
        child_procs = proc.children()
        if child_procs:
            parts = []
            line_sep = Text('\n')
            for child in child_procs:
                try:
                    parts.append(Text.assemble((str(child.pid), 'number'), ':', child.name(),
                                                ' - ', (child.status(), 'important')))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    parts.append(Text.assemble((str(child.pid), 'number'), ': N/A (No access or exited)'))
            table.add_row('Children:', line_sep.join(parts))

    connections = data.get('net_connections')
    if connections is not None: # Check if connections info was obtainable
        table.add_row('# INET Con.:', Text(str(len(connections))), end_section=True)
    else:
        table.add_row('# INET Con.:', NOT_AVAILABLE)


    cpu_times = data.get('cpu_times')
    if cpu_times:
        table.add_row('CPU User Time:', Text(f"{cpu_times.user:.2f}s"))
        table.add_row('CPU System Time:', Text(f"{cpu_times.system:.2f}s"))
        has_iowait = hasattr(cpu_times, 'iowait') and cpu_times.iowait is not None
        if has_iowait:
            table.add_row('CPU I/O Wait:', Text(f"{cpu_times.iowait:.2f}s"), end_section=True)
        else:
            table.add_row('', '', end_section=True) # Just to close the section visually
    else:
        table.add_row('CPU Times:', NOT_AVAILABLE)


    memory_info = data.get('memory_info')
    if memory_info:
        table.add_row('Memory RSS:', Text(format_size(memory_info.rss)))
        table.add_row('Memory VMS:', Text(format_size(memory_info.vms)), end_section=True)
    else:
        table.add_row('Memory Info:', NOT_AVAILABLE)

    io_counters = data.get('io_counters')
    if io_counters:
        table.add_row('I/O Read Count:', Text(f"{io_counters.read_count:,}"))
        table.add_row('I/O Write Count:', Text(f"{io_counters.write_count:,}"))
        table.add_row('I/O Bytes Read:', Text(format_size(io_counters.read_bytes)))
        table.add_row('I/O Bytes Written: ', Text(format_size(io_counters.write_bytes)),
                    end_section=True)
    else:
        table.add_row('I/O Counters:', NOT_AVAILABLE)

    console.print(table)

@app.command()
def stop_daemon(
    pid: Annotated[int, typer.Argument(metavar='PID', autocompletion=pid_completer,
                                       help="The Process ID of the daemon to stop")]
    ) -> None:
    """Stops a running Saturnin daemon process.

    This command attempts a graceful shutdown by sending the appropriate
    signal (SIGINT on Unix, CTRL_C_EVENT on Windows) to the daemon.
    """
    #if not psutil.pid_exists(pid):
        #console.print_error("Process not found")
        #return
    #daemon.stop_daemon(pid)
    try:
        if not psutil.pid_exists(pid):
            console.print_error(f"Process with PID [item]{pid}[/] not found.")
            return
        psutil.Process(pid) # To confirm it's a real process
    except psutil.NoSuchProcess:
        console.print_error(f"Process with PID [item]{pid}[/] not found (or exited just now).")
        return
    except psutil.AccessDenied:
        console.print_error(f"Access denied when checking PID [item]{pid}[/]. Cannot proceed to stop.")
        return

    console.print(f"Attempting to stop daemon with PID [item]{pid}[/]... ", end="")
    try:
        daemon.stop_daemon(pid) # This calls `saturnin-daemon stop <pid>`
        # `stop_daemon` will raise an error if `saturnin-daemon stop` fails or times out.
    except Exception:
        console.print('[warning]ERROR')
        console.print_exception(show_locals=False) # Show traceback for the error from stop_daemon
    else:
        console.print('[ok]OK')

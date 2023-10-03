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
# pylint: disable=R0912, R0913, R0914, R0915

"""Saturnin daemon commands


"""

from __future__ import annotations
from typing import Dict, List
import datetime
import psutil
import typer
from rich.table import Table
from rich.text import Text
from rich import box
from saturnin.base import directory_scheme
from saturnin.component.recipe import RecipeInfo, recipe_registry
from saturnin.lib.console import console
from saturnin.lib import daemon

#: Typer command group for daemon management commands
app = typer.Typer(rich_markup_mode="rich", help="Saturnin daemons.")

def get_first_line(text: str) -> str:
    """Returns first non-empty line from argument.
    """
    return text.strip().split('\n')[0]

def get_running_daemons() -> Dict[int, str]:
    """Returns dictionary with running daemons: key=pid, value=recipe_name
    """
    result = {}
    for pid_file in directory_scheme.pids.glob('*.pid'):
        recipe_name = pid_file.read_text()
        pid = int(pid_file.stem)
        if psutil.pid_exists(pid):
            result[pid] = recipe_registry.get(recipe_name)
        else:
            pid_file.unlink()
    return result

def pid_completer(ctx, args, incomplete) -> List:
    """Click completer for PIDs of running Saturnin daemons.
    """
    return [(str(pid), recipe.name if recipe else "")
            for pid, recipe in get_running_daemons().items()]

def format_size(size: int, decimals: int=2, binary_system: bool=True) -> str:
    """Returns "humanized" size.
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
    """List running Saturnin daemons.
    """
    daemons = get_running_daemons()
    #
    if daemons:
        table = Table(title='Running daemons', box=box.ROUNDED)
        table.add_column('PID', style='cyan')
        table.add_column('Status', style='bold yellow')
        table.add_column('Recipe', style='green')
        table.add_column('Description', style='white')
        recipe: RecipeInfo = None
        for pid, recipe in daemons.items():
            if recipe is None:
                table.add_row(str(pid), psutil.Process(pid).status(), 'UNKNOWN',
                              "[warning]Recipe used by daemon was uninstalled")
            else:
                table.add_row(str(pid), psutil.Process(pid).status(), recipe.name,
                              get_first_line(recipe.description))
        console.print(table)
    else:
        console.print("There are no Saturnin demons running.")


@app.command()
def show_daemon(pid: int=typer.Argument(..., metavar='PID', autocompletion=pid_completer)) -> None:
    """Show information about running Saturnin daemon.
    """
    if not psutil.pid_exists(pid):
        console.print_error("Process not found")
        return
    proc = psutil.Process(pid)
    data = proc.as_dict(ad_value='[important]N/A[/]')
    created = datetime.datetime.fromtimestamp(data['create_time'])
    run_time = datetime.datetime.now() - created
    table = Table(title=f"  Process [important]{pid}", box=box.ROUNDED, show_header=False,
                  title_justify='left')
    table.add_column('', style='green')
    table.add_column('')
    #
    table.add_row('Status:', Text(data['status'], style='important'))
    table.add_row('Created:', Text(created.strftime("%Y-%m-%d %H:%M:%S")))
    table.add_row('Run time:', Text(str(run_time)), end_section=True)

    table.add_row('# threads:', Text(str(data['num_threads'])))
    if 'num_handles' in data:
        table.add_row('# handles:', Text(str(data['num_handles'])))
    if 'num_fds' in data:
        table.add_row('# files:', Text(str(data['num_fds'])))
    children = proc.children()
    if children:
        parts = []
        line_sep = Text('\n')
        for child in children:
            parts.append(Text.assemble((str(child.pid), 'number'), ':', child.name(), ' - ', (child.status(), 'important')))
        table.add_row('Children:', line_sep.join(parts))
    table.add_row('# INET con.:', Text(str(len(data['connections']))), end_section=True)

    table.add_row('Name:', Text(data['name'], style='cyan'))
    table.add_row('Executable:', Text(data['exe']))
    table.add_row('Cmd. line:', Text(', '.join(data['cmdline'])))
    table.add_row('CWD:', Text(data['cwd']))
    table.add_row('User:', Text(data['username']), end_section=True)

    has_iowait = hasattr(data['cpu_times'], 'iowait')
    table.add_row('CPU user:', Text(str(data['cpu_times'].user)))
    table.add_row('CPU system:', Text(str(data['cpu_times'].system)),
                  end_section=not has_iowait)
    if has_iowait:
        table.add_row('CPU I/O wait:', Text(str(data['cpu_times'].iowait)), end_section=True)

    table.add_row('RSS (bytes):', Text(format_size(data['memory_info'].rss)))
    table.add_row('VMS (bytes):', Text(format_size(data['memory_info'].vms)), end_section=True)

    table.add_row('Read count:', Text(str(data['io_counters'].read_count)))
    table.add_row('Write count:', Text(str(data['io_counters'].write_count)))
    table.add_row('Bytes read:', Text(str(data['io_counters'].read_bytes)))
    table.add_row('Bytes written: ', Text(str(data['io_counters'].write_bytes)),
                  end_section=True)

    console.print(table)

@app.command()
def stop_daemon(pid: int=typer.Argument(..., metavar='PID', autocompletion=pid_completer)) -> None:
    """Stop running Saturnin daemon.
    """
    if not psutil.pid_exists(pid):
        console.print_error("Process not found")
        return
    daemon.stop_daemon(pid)

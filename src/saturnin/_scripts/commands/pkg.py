#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/pkg.py
# DESCRIPTION:    Saturnin package manager commands
# CREATED:        19.1.2021
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
# Copyright (c) 2021 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin package manager commands


"""

from __future__ import annotations
from typing import List
import subprocess
from operator import attrgetter
from rich.table import Table
from rich import box
import typer
from saturnin.base import site
from saturnin.component.registry import get_service_distributions, service_registry

app = typer.Typer(rich_markup_mode="rich", help="Package management.")

@app.command('services')
def list_services(with_name: str=typer.Option('', help="List only services with this string in name")):
    "List installed Saturnin services."
    table = Table(title='Registered services', box=box.ROUNDED)
    table.add_column('Service', style='green')
    table.add_column('Version', style='yellow')
    table.add_column('UID', style='white')
    table.add_column('Distribution', style='white')
    l = list(service_registry.filter(lambda x: with_name in x.name))
    l.sort(key=attrgetter('name'))
    for svc in l:
        table.add_row(svc.name, svc.version, str(svc.uid), svc.distribution)
    site.console.print(table)

@app.command('distributions')
def list_distributions():
    "List installed distribution packages with Saturnin components."
    table = Table(title='Installed distributions', box=box.ROUNDED)
    table.add_column('Distribution', style='white')
    table.add_column('Version', style='yellow')
    for dist in get_service_distributions():
        table.add_row(dist.metadata['name'], dist.version)
    site.console.print(table)

@app.command()
def pip(args: List[str]=typer.Argument(None, help="Arguments for pip.")):
    "Run 'pip' package manager in Saturnin virtual environment."
    pip_cmd = [str(site.pip_path)]
    if 'uninstall' in args:
        args.append('-y')
    pip_cmd.extend(args)
    result = subprocess.run(pip_cmd, capture_output=True, text=True)
    site.print(result.stdout)
    if result.returncode != 0:
        site.err_console.print(result.stderr)
    elif 'install' in args or 'uninstall' in args:
        update_registry()

@app.command('registry')
def update_registry():
    """Updates registry of installed Saturnin components.

    The registry is updated automatically when Saturnin packages are installed/uninstalled
    with built-in 'pip' command. Manual update is required only when packages are
    added/updated/removed in differet way.
    """
    site.print('Updating Saturnin component registry ... ', end='')
    try:
        service_registry.clear()
        service_registry.load_from_installed()
        site.save_components()
        site.print('[bold yellow]OK')
    except Exception as exc:
        site.print('[bold red]ERROR')
        site.print_exception(exc)

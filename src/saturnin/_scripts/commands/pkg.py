# SPDX-FileCopyrightText: 2021-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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
 # pylint: disable=W1510

"""Saturnin package manager commands


"""

from __future__ import annotations
from typing import List
import subprocess
from uuid import UUID
from re import sub
from operator import attrgetter
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
import typer
from firebird.uuid import oid_registry
from saturnin.base import directory_scheme, RESTART
from saturnin.component.recipe import recipe_registry
from saturnin.component.registry import service_registry, ServiceInfo
from saturnin.component.apps import application_registry, ApplicationInfo
from saturnin.lib.console import console, _h, RICH_YES, RICH_NO
from saturnin.lib.metadata import distribution
from saturnin._scripts.completers import service_completer, application_completer, get_first_line

#: Typer command group for package management commands
app = typer.Typer(rich_markup_mode="rich", help="Package management.")

@app.command()
def list_services(with_name: str= \
                    typer.Option('',help="List only services with this string in name")):
    "Lists installed Saturnin services."
    services = list(service_registry.filter(lambda x: with_name in x.name))
    services.sort(key=attrgetter('name'))
    if services:
        table = Table(title='Registered services' if not with_name
                      else f"Registered services with name containing '{with_name}'",
                      box=box.ROUNDED)
        table.add_column('Service', style='green')
        table.add_column('Version', style='number')
        table.add_column('Description')
        for svc in services:
            table.add_row(svc.name, svc.version, get_first_line(svc.description))
        console.print(table)
    else:
        console.print("There are no Saturnin services registered.")

@app.command()
def show_service(service_id: str=typer.Argument('', help="Service UID or name",
                                                autocompletion=service_completer)):
    "Show information about installed service."
    svc: ServiceInfo = None
    try:
        svc = service_registry.get(UUID(service_id))
    except Exception: # pylint: disable=W0703
        svc = service_registry.get_by_name(service_id)
    if svc is None:
        console.print_error('Service not registered!')
        return

    api = []
    for uid in svc.api:
        inf: ServiceInfo = oid_registry.get(uid)
        api.append(str(uid) if inf is None else inf.name)

    vendor = oid_registry.get(svc.vendor)
    vendor = Text(str(svc.vendor), style='yellow') if vendor is None else Text(vendor.description)

    table = Table.grid()
    table.add_column(style='green')
    table.add_column()
    table.add_row('UID:', Text(str(svc.uid), style='yellow'))
    table.add_row('Name:', Text(svc.name))
    table.add_row('Version:', Text(svc.version, style='cyan'))
    table.add_row('Vendor:', vendor)
    table.add_row('Classification: ', Text(svc.classification))
    table.add_row('Description:', Text(svc.description))
    table.add_row('Facilities:', Text(', '.join(svc.facilities)))
    table.add_row('API:', Text(', '.join(api), style='yellow'))
    table.add_row('Distribution:', Text(svc.distribution))
    console.print(table)

@app.command()
def list_applications(with_name: str= \
                      typer.Option('',help="List only applications with this string in name")):
    "Lists installed Saturnin applications."
    apps = list(application_registry.filter(lambda x: with_name in x.name))
    apps.sort(key=attrgetter('name'))
    if apps:
        table = Table(title='Registered applications' if not with_name
                      else f"Registered applications with name containing '{with_name}'",
                      box=box.ROUNDED)
        table.add_column('Application', style='green')
        table.add_column('Version', style='number')
        table.add_column('Used', width=9, justify='center')
        table.add_column('Description')
        for app in apps:
            table.add_row(app.name, app.version, RICH_YES if
                          recipe_registry.any(lambda x: x.application is not None
                                              and x.application == app.uid)
                          else RICH_NO, get_first_line(app.description))
        console.print(table)
    else:
        console.print("There are no Saturnin applications registered.")

@app.command()
def show_application(app_id: str=typer.Argument('', help="Application UID or name",
                                                    autocompletion=application_completer)):
    "Show information about installed application."
    app: ApplicationInfo = None
    try:
        app = application_registry.get(UUID(app_id))
    except Exception: # pylint: disable=W0703
        app = application_registry.get_by_name(app_id)
    if app is None:
        console.print_error('Application not registered!')
        return

    vendor = oid_registry.get(app.vendor)
    vendor = _h(Text(str(app.vendor) if vendor is None else vendor.description))

    table = Table.grid()
    table.add_column(style='green')
    table.add_column()
    table.add_row('UID:', _h(Text(str(app.uid))))
    table.add_row('Name:', Text(app.name))
    table.add_row('Version:', _h(Text(app.version)))
    table.add_row('Vendor:', vendor)
    table.add_row('Classification: ', Text(app.classification))
    table.add_row('Description:', Text(app.description))
    table.add_row('Distribution:', Text(app.distribution))
    console.print(table)

@app.command()
def list_packages():
    """Lists installed distribution packages with Saturnin components.

    This command does not list ALL packages installed in Saturnin virtual environment, but
    only those that contain registered Saturnin components. To list all installed packages,
    use: **pip list**.
    """
    packages = set(service_registry.report('item.distribution'))
    packages.update(application_registry.report('item.distribution'))
    if packages:
        table = Table(title='Installed Saturnin packages', box=box.ROUNDED)
        table.add_column('Package', style='green')
        table.add_column('Version', style='number')
        for dist in (distribution(pkg) for pkg in packages):
            table.add_row(dist.metadata['name'], dist.version)
        console.print(table)
    else:
        console.print("No Saturnin packages are installed.")

@app.command()
def update_registry():
    """Updates registry of installed Saturnin components.

    The registry is updated automatically when Saturnin packages are manipulated with
    built-in **install**, **uninstall** or **pip** commands. Manual update is required only
    when packages are added/updated/removed in differet way.
    """
    console.print('Updating Saturnin service registry ... ', end='')
    try:
        service_registry.clear()
        service_registry.load_from_installed()
        service_registry.save()
        console.print('[ok]OK')
    except Exception: # pylint: disable=W0703
        console.print('[warning]ERROR')
        console.print_exception()
    console.print('Updating Saturnin application registry ... ', end='')
    try:
        application_registry.clear()
        application_registry.load_from_installed()
        application_registry.save()
        console.print('[ok]OK')
    except Exception: # pylint: disable=W0703
        console.print('[warning]ERROR')
        console.print_exception()

@app.command()
def pip(args: List[str]=typer.Argument(None, help="Arguments for pip.")):
    """Runs 'pip' package manager in Saturnin virtual environment.
    """
    pip_cmd = directory_scheme.get_pip_cmd()
    pip_cmd.extend(args)
    if '--help' in args:
        result = subprocess.run(pip_cmd, capture_output=True, text=True) # pylint: disable=W1510
        console.print(_h(Text(pip.__doc__ + result.stdout)))
    else:
        result = subprocess.run(pip_cmd) # pylint: disable=W1510
    if result.returncode != 0:
        console.err_console.print(result.stderr)
    elif '--help' not in args and ('install' in args or 'uninstall' in args):
        update_registry()

@app.command()
def install_package(args: List[str]=typer.Argument(..., help="Arguments for pip install.")):
    """Installs Python package into Saturnin virtual environment via 'pip'.

Note:
   This command is used also to upgrade installed packages using '-U' or '--upgrade' option.
    """
    pip_cmd = directory_scheme.get_pip_cmd('install')
    pip_cmd.extend(args)
    if '--help' in args:
        result = subprocess.run(pip_cmd, capture_output=True, text=True) # pylint: disable=W1510
        text = install_package.__doc__ + sub(r'(\bpip install\b)', 'install package',
                                             result.stdout)
        text = sub(r'(?s)\b(?:Description:).+(?:Install Options:)', "Install Options:",
                   text)
        console.print(_h(Text(text)))
        return None
    #
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        progress.add_task("Installing...", total=1)
        result = subprocess.run(pip_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
    if result.returncode != 0:
        console.err_console.print(result.stdout)
    update_registry()
    return RESTART

@app.command()
def uninstall_package(args: List[str]=typer.Argument(..., help="Arguments for pip uninstall.")):
    """Uninstalls Python package from Saturnin virtual environment via `pip`.
    """
    pip_cmd = directory_scheme.get_pip_cmd('uninstall')
    pip_cmd.append('--yes')
    pip_cmd.extend(args)
    if '--help' in args:
        result = subprocess.run(pip_cmd, capture_output=True, text=True)
        text = uninstall_package.__doc__ + sub(r'(\bpip uninstall\b)', 'uninstall package',
                                               result.stdout)
        text = sub(r'(?s)\b(?:Description:).+(?:Uninstall Options:)', "Uninstall Options:",
                   text)
        console.print(_h(Text(text)))
        return None
    #
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        progress.add_task("Uninstalling...", total=1)
        result = subprocess.run(pip_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
    if result.returncode != 0:
        console.err_console.print(result.stdout)
    update_registry()
    return RESTART

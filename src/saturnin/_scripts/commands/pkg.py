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

"""Typer commands for managing Saturnin components and Python packages within its environment.

This includes listing and inspecting registered services and applications,
updating Saturnin's component registries, and wrappers around `pip` for
installing and uninstalling packages while ensuring registry consistency.
"""

from __future__ import annotations

import subprocess
from operator import attrgetter
from re import sub
from typing import Annotated
from uuid import UUID

import typer
from rich import box
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from saturnin._scripts.completers import application_completer, get_first_line, service_completer
from saturnin.base import RESTART, directory_scheme
from saturnin.component.apps import ApplicationInfo, application_registry
from saturnin.component.recipe import RecipeInfo, recipe_registry
from saturnin.component.registry import ServiceInfo, service_registry
from saturnin.lib.console import RICH_NO, RICH_YES, RICH_NA, _h, console
from saturnin.lib.metadata import distribution

from firebird.uuid import OIDNode, oid_registry

#: Typer command group for package management commands
app = typer.Typer(rich_markup_mode="rich", help="Package management.")

APP_TYPE_CMD = 'Command'
APP_TYPE_RECIPE = 'Recipe'

@app.command()
def list_services(
    with_name: Annotated[str, typer.Option(help="List only services with this string in name")]=''
    ):
    "Lists Saturnin services registered in the local environment."
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
def show_service(
    service_id: Annotated[str, typer.Argument(help="Service UID or name",
                                              autocompletion=service_completer)]=''
    ):
    "Shows detailed information about a specific registered Saturnin service."
    svc: ServiceInfo = None
    try:
        svc = service_registry.get(UUID(service_id))
    except Exception:
        svc = service_registry.get_by_name(service_id)
    if svc is None:
        console.print_error('Service not registered!')
        return

    api = []
    for uid in svc.api:
        inf: ServiceInfo = oid_registry.get(uid)
        api.append(str(uid) if inf is None else inf.name)

    vendor: OIDNode = oid_registry.get(svc.vendor)
    vendor: Text = Text(str(svc.vendor), style='yellow') if vendor is None else Text(vendor.description)

    table = Table.grid(padding=(0, 1, 0, 1))
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
    console.print(Panel(table, title='[title]Saturnin service', title_align='left',
                        box=box.ROUNDED, padding=(1,2)))

@app.command()
def list_applications(
    with_name: Annotated[str, typer.Option(help="List only applications with this string in name")]=''
    ):
    """Lists Saturnin applications registered in the local environment.
    Includes an indicator if the application is currently used by any installed recipe.
    """
    apps = list(application_registry.filter(lambda x: with_name in x.name))
    apps.sort(key=attrgetter('name'))
    if apps:
        table = Table(title='Registered applications' if not with_name
                      else f"Registered applications with name containing '{with_name}'",
                      box=box.ROUNDED)
        table.add_column('Application', style='green')
        table.add_column('Version', style='number')
        table.add_column('Type')
        table.add_column('Used', width=9, justify='center')
        table.add_column('Description')
        app_info: ApplicationInfo
        for app_info in apps:
            if app_info.is_command():
                is_used = RICH_NA
                app_type = APP_TYPE_CMD
            else:
                is_used = RICH_YES if recipe_registry.app_is_used(app_info.uid) else RICH_NO
                app_type = APP_TYPE_RECIPE
            table.add_row(app_info.name, app_info.version, app_type, is_used,
                          get_first_line(app_info.description))
        console.print(table)
    else:
        console.print("There are no Saturnin applications registered.")

@app.command()
def show_application(
    app_id: Annotated[str, typer.Argument(help="Application UID or name",
                                          autocompletion=application_completer)]=''
    ):
    "Shows detailed information about a specific registered Saturnin application."
    app: ApplicationInfo = None
    try:
        app = application_registry.get(UUID(app_id))
    except Exception:
        app = application_registry.get_by_name(app_id)
    if app is None:
        console.print_error('Application not registered!')
        return

    vendor: OIDNode = oid_registry.get(app.vendor)
    vendor = _h(Text(str(app.vendor) if vendor is None else vendor.description))

    table = Table.grid(padding=(0, 1, 0, 1))
    table.add_column(style='green')
    table.add_column()
    table.add_row('UID:', _h(Text(str(app.uid))))
    table.add_row('Name:', Text(app.name))
    table.add_row('Version:', _h(Text(app.version)))
    table.add_row('Vendor:', vendor)
    table.add_row('Classification:', Text(app.classification))
    table.add_row('Type:', Text(APP_TYPE_CMD if app.is_command() else APP_TYPE_RECIPE))
    if not app.is_command():
        recipe_list = ', '.join(recipe.name for recipe in recipe_registry.get_recipes_with_app(app.uid))
        if recipe_list:
            table.add_row('Installed recipes: ', recipe_list)
    table.add_row('Description:', Text(app.description))
    table.add_row('Distribution:', Text(app.distribution))
    console.print(Panel(table, title='[title]Saturnin application', title_align='left',
                        box=box.ROUNDED, padding=(1,2)))

@app.command()
def list_packages():
    """Lists installed distribution packages that provide Saturnin components.

    This command does not list ALL packages installed in Saturnin's virtual environment,
    but only those that have registered Saturnin services or applications.
    To list all installed packages, use the `pip list` command.
    """
    packages = set(service_registry.report('item.distribution'))
    packages.update(application_registry.report('item.distribution'))
    if packages:
        table = Table(title='Installed Saturnin packages', box=box.ROUNDED)
        table.add_column('Package', style='green')
        table.add_column('Version', style='number')
        for pkg_name in sorted(packages): # Sort for consistent output
            dist_obj = distribution(pkg_name)
            if dist_obj: # Ensure distribution object was found
                table.add_row(dist_obj.metadata['name'], dist_obj.version)
            else:
                table.add_row(pkg_name, "[dim]version unknown[/dim]") # Handle if dist somehow not found
        console.print(table)
    else:
        console.print("No packages with Saturnin components are installed..")

@app.command()
def update_registry():
    """Updates Saturnin's registries of installed services and applications.

    The registries are updated automatically when Saturnin packages are managed
    with the built-in `install-package`, `uninstall-package`, or `pip install/uninstall`
    commands. Manual update is required only when packages are added, updated,
    or removed in a different way (e.g., using an external `pip` directly or
    manually altering the Python environment).
    """
    console.print('Updating Saturnin service registry ... ', end='')
    try:
        service_registry.clear()
        service_registry.load_from_installed()
        service_registry.save()
        console.print('[ok]OK')
    except Exception:
        console.print('[warning]ERROR')
        console.print_exception()
    console.print('Updating Saturnin application registry ... ', end='')
    try:
        application_registry.clear()
        application_registry.load_from_installed()
        application_registry.save()
        console.print('[ok]OK')
    except Exception:
        console.print('[warning]ERROR')
        console.print_exception()

@app.command()
def pip(args: Annotated[list[str] | None, typer.Argument(help="Arguments for pip.")]=None):
    """Runs the 'pip' package manager within Saturnin's virtual environment.

    This command acts as a direct passthrough to `pip`, allowing access to all
    its functionalities (e.g., `pip search`, `pip show`, `pip freeze`).

    For installing or uninstalling packages that provide Saturnin components,
    it's generally recommended to use the more specific `install-package`
    and `uninstall-package` commands. These ensure that Saturnin's internal
    component registries are updated automatically.

    However, if `pip install` or `pip uninstall` are invoked via this generic
    `pip` command, Saturnin will subsequently attempt to update its component
    registries to reflect potential changes.

    The output of `pip --help` (or help for any pip subcommand) is also available
    by passing the respective arguments.
    """
    if args is None:
        args = []
    pip_cmd = directory_scheme.get_pip_cmd()
    pip_cmd.extend(args) # Ensure args is not None
    if ('--help' in args) or ('-h' in args):
        result = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
        if len(args) == 1 and args[0] == '--help':
            # Show our docstring first, then pip's output
            help_text = pip.__doc__ + "\n--- pip output ---\n" + result.stdout
        else:
            # Show only pip's output
            help_text = result.stdout
        console.print(_h(Text(help_text)))
    else:
        result = subprocess.run(pip_cmd, check=False)
    if result.returncode != 0:
        # pip already prints its errors to stderr, so no need to print result.stderr
        # unless it was suppressed, which it isn't here.
        # We might log this failure if Saturnin had more extensive internal logging.
        console.print_error(f"'pip {' '.join(args or [])}' failed with exit code {result.returncode}.")
    elif '--help' not in args and ('install' in args or 'uninstall' in args):
        update_registry()

@app.command()
def install_package(args: Annotated[list[str], typer.Argument(help="Arguments for pip install.")]):
    """Installs or upgrades Python packages in Saturnin's virtual environment using 'pip'.

    After the pip operation, Saturnin's component registries (services, applications)
    are automatically updated to reflect any changes. This command is recommended
    for managing packages that provide Saturnin components.

    Supports all standard `pip install` options, including upgrading packages
    (e.g., using `-U` or `--upgrade`).
    """
    pip_cmd = directory_scheme.get_pip_cmd('install')
    pip_cmd.extend(args)
    if '--help' in args:
        result = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
        text = install_package.__doc__ + sub(r'(\bpip install\b)', 'install package',
                                             result.stdout)
        text = sub(r'(?s)\b(?:Description:).+(?:Install Options:)', "Install Options:",
                   text)
        console.print(_h(Text(text)))
        return None
    #
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        progress.add_task("Installing packages...", total=None)
        result = subprocess.run(pip_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, check=False)
    if result.returncode != 0:
        console.print("[bold red]Installation failed. Output from pip:[/bold red]")
        console.print(result.stdout) # Show pip output on failure
    else:
        console.print("[bold green]Installation successful.[/bold green]")
    update_registry()
    return RESTART

@app.command()
def uninstall_package(args: Annotated[list[str], typer.Argument(help="Arguments for pip uninstall.")]):
    """Uninstalls Python packages from Saturnin's virtual environment using 'pip'.

    After the pip operation, Saturnin's component registries (services, applications)
    are automatically updated. This command is recommended for removing packages
    that provide Saturnin components.

    The `--yes` option is automatically passed to `pip uninstall` to avoid
    interactive prompts from pip.
    """
    pip_cmd = directory_scheme.get_pip_cmd('uninstall')
    pip_cmd.append('--yes')
    pip_cmd.extend(args)
    if '--help' in args:
        result = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
        text = uninstall_package.__doc__ + sub(r'(\bpip uninstall\b)', 'uninstall package',
                                               result.stdout)
        text = sub(r'(?s)\b(?:Description:).+(?:Uninstall Options:)', "Uninstall Options:",
                   text)
        console.print(_h(Text(text)))
        return None
    #
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        progress.add_task("Uninstalling packages...", total=None)
        result = subprocess.run(pip_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, check=False)
    if result.returncode != 0:
        console.print("[bold red]Uninstallation failed. Output from pip:[/bold red]")
        console.print(result.stdout)
    else:
        console.print("[bold green]Uninstallation successful.[/bold green]")
    update_registry()
    return RESTART

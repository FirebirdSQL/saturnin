# SPDX-FileCopyrightText: 2021-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/cli.py
# DESCRIPTION:    Script for Saturnin CLI manager
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
# pylint: disable=W0212, C0301, W0703, W0622

"""Saturnin CLI manager.

---

\b
When invoked without additional parameters, it's activated in **console** mode.
This mode runs REPL that provides advanced functionality like command and parameter completion,
interactive help and persistent command history. The command set available in this mode
may differ from command set available in **direct** mode (see below).

When saturnin is invoked with additional parameters, it executes specified command and exists.
Some commands (typically those required to run only once or not very often like *initialize*
or *create home*) are available only in this **direct** mode.
"""

# group commands
# LIST - print list of items (services, nodes, packages etc.)
# SHOW - print details about particular item
# EDIT - Edit items (configuration etc.)
# CREATE - create item
# RUN - run components
# START - ??
# STOP - Stop activities (daemons, notifications, trace, logging)
# INSTALL - install components via pip
# UNINSTALL - uninstall components via pip
# UPDATE - Update items (components, OIDs etc.)

from __future__ import annotations
from typing import Callable, List, Tuple, Optional
import sys
from typer import Typer, Context
from rich.align import Align
from rich.padding import Padding
from rich.markdown import Markdown
from saturnin.component.recipe import recipe_registry
from saturnin.component.apps import application_registry
from saturnin.component.registry import iter_entry_points
from saturnin.lib.console import console
# from saturnin.lib import wingdbstub
from .repl import repl, IOManager
from .commands.recipes import run_recipe
from .completers import get_first_line

#: REPL introductory markdown text
REPL_INTRO = Markdown("""
# Saturnin management console

Saturnin was invoked in **console** mode that provides command and parameter completion,
interactive help and persistent command history. The command set available in this mode may
differ from command set available in **direct** mode (see below).

When saturnin is invoked with additional parameters, it executes specified command and exists.
Some commands (typically those required to run only once or not very often like *initialize*
or *create home*) are available only in this **direct** mode.

---
""")

#: REPL help text
REPL_HELP = """Type '?' or '?<command>' for help.
Type 'quit' to leave the console.
Use 'Ctrl+Space' to activate command completion.
"""

#: Standard command groups
#: List of (command name, short help) tuples
command_groups: List[Tuple[str,str]] = [
    ('list', "Print list of items (services, nodes, packages etc.)"),
    ('show', "Print details about particular item (service, node, package etc.)"),
    ('edit', "Edit item (configuration, recipe etc.)"),
    ('create', "Create item (configuration, recipe etc.)"),
    ('run', "Run Saturnin components (recipes, applications, utilities etc.)"),
    ('update', "Update items (components, OIDs etc.)"),
    ('stop', "Stop activities (daemons, notifications, trace, logging)"),
    ('install', "Install components (packages, recipes etc.)"),
    ('uninstall', "Uninstall components (packages, recipes etc.)"),
]


def find_group(in_app: Typer, name: str) -> Typer:
    """Returns sub-command group in command group.

    Arguments:
      in_app: Typer instance to be searched.
      name:   Command name.

    Returns: Typer instance for command.
    """
    for grp in in_app.registered_groups:
        if grp.name == name:
            return grp.typer_instance
    return None

def add_command(app: Typer, name: str, cmd: Callable, *, help: Optional[str]=None,
                panel: Optional[str]=None) -> None: # pylint: disable=W0622
    """Add command into main Typer application.

    Arguments:
       app:   Typer instance under which the command should be placed.
       name:  Command name. Can use dot notation to create a sub-command.
       cmd:   Callable to be registered as Typer command.
       help:  Optional help for command.
       pabel: Rich panel where command should be listed in help.
    """
    names: List[str] = name.split('.')
    group: Typer = app
    for group_name in names[:-1]:
        sub_group = find_group(group, group_name)
        if sub_group is None:
            sub_group = Typer(name=group_name)
            group.add_typer(sub_group)
            group = sub_group
        else:
            group = sub_group
    group.command(name=names[-1], help=help, rich_help_panel=panel)(cmd)

def cli_loop(*, restart: bool) -> bool:
    """Main CLI loop via Typer.

    Arguments:
      restart: True when CLI was restarted.

    Returns:
      True if CLI restart is required (to reload commands etc.). False means "normal" end.
    """
    def replcheck(ctx: Context):
        """This method start REPL when CLI is started without subcommand.
        """
        if not app._in_repl and ctx.invoked_subcommand is None:
            app._in_repl = True
            if not app._restart:
                console.print(Padding(Align(REPL_INTRO, pad=False,),(1, 1, 1, 1),))
                console.print(Padding(Align(REPL_HELP, pad=False,),(0, 1, 0, 1),))
            else:
                ctx.command.help = ''
            with IOManager(ctx) as ioman:
                app._restart = repl(ctx, ioman)

    app: Typer = None
    going_repl = len(sys.argv) == 1
    if going_repl:
        app = Typer(rich_markup_mode="markdown", epilog=REPL_HELP)
    else:
        app = Typer(rich_markup_mode="markdown", help=__doc__)
    app._in_repl = False
    app._restart = restart
    app.callback(invoke_without_command=True)(replcheck)
    # Install command groups
    for group_name, group_help in command_groups:
        app.add_typer(Typer(), name=group_name, help=group_help)
    # Install registered commands
    for entry in iter_entry_points('saturnin.commands'):
        try:
            add_command(app, entry.name, entry.load())
        except Exception as exc:
            console.print_error(f"Cannot install command '{entry.name}'\n{exc!s}")
    if going_repl:
        for entry in iter_entry_points('saturnin.repl_only_commands'):
            try:
                add_command(app, entry.name, entry.load())
            except Exception as exc:
                console.print_error(f"Cannot install command '{entry.name}'\n{exc!s}")
    else:
        for entry in iter_entry_points('saturnin.no_repl_commands'):
            try:
                add_command(app, entry.name, entry.load())
            except Exception as exc:
                console.print_error(f"Cannot install command '{entry.name}'\n{exc!s}")
    # Install registered recipes
    for recipe in recipe_registry.values():
        if recipe.application is None:
            try:
                add_command(app, f'run.{recipe.name}', run_recipe,
                            help=recipe.description)
            except Exception as exc:
                console.print_error(f"Cannot install command '{recipe.name}'\n{exc!s}")
        else:
            application = application_registry.get(recipe.application)
            if application is None:
                console.print_error(f"Cannot install recipe {recipe.name} due to missing application.")
                continue
            try:
                add_command(app, f'run.{recipe.name}', application.factory_obj,
                            help=get_first_line(recipe.description))
            except Exception as exc:
                console.print_error(f"Cannot install command '{recipe.name}'\n{exc!s}")
    #
    app(standalone_mode=False)
    return app._restart

def main():
    """Main entry point for Saturnin CLI manager.
    """
    restart = False
    while restart := cli_loop(restart=restart):
        pass

if __name__ == '__main__':
    main()

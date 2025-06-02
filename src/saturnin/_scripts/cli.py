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

"""# Saturnin management console

The primary tool for interacting with Saturnin via the command line.
It operates in two primary modes:

1.  **Console Mode (REPL)**:

When invoked without any commands or arguments (i.e., just `saturnin`),
it launches an interactive Read-Eval-Print Loop. The set of commands available in console
mode might differ slightly from direct mode.
This mode offers enhanced features such as:

*   Command and parameter auto-completion.

*   Interactive help (`?` or `?<command>`).

*   Persistent command history.

2.  **Direct Mode**:

When invoked with a command and its arguments (e.g., `saturnin list services`), it executes
the specified command directly and then exits. Some commands, particularly those for one-time
setup or infrequent operations (like `initialize` or `create home`), are typically available
only in this mode. For technical reasons, commands `pip`, `install package` and `uninstall package`
are available only in **console mode**.

---

\b
The CLI dynamically loads commands from registered entry points, including
core commands, application-specific commands, and commands generated from
installed recipes.
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

import os
import sys
from collections.abc import Callable

from rich.align import Align
from rich.markdown import Markdown
from rich.padding import Padding
from saturnin.component.apps import ApplicationInfo, application_registry
from saturnin.component.recipe import RecipeInfo, recipe_registry
from saturnin.component.registry import iter_entry_points
from saturnin.lib.console import console
from typer import Context, Typer

from .commands.recipes import run_recipe
from .completers import get_first_line

# from saturnin.lib import wingdbstub
from .repl import IOManager, repl

#: Introductory Markdown text displayed when the REPL starts for the first time.
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

#: Brief help text displayed in the REPL, guiding users on basic interactions.
REPL_HELP = """Type '?' or '?<command>' for help.
Type 'quit' to leave the console.
Use 'Ctrl+Space' to activate command completion.
"""

#: Standard command groups used to organize commands in the Typer help output.
#: Each tuple contains (command_group_name, short_help_description).
command_groups: list[tuple[str,str]] = [
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

def find_group(in_app: Typer, name: str) -> Typer | None:
    """Finds and returns a registered Typer sub-command group by its name.

    Arguments:
      in_app: The parent Typer application or group to search within.
      name: The name of the sub-command group to find.

    Returns:
        The Typer instance of the found sub-command group, or `None` if no group with
        the given name is registered under `in_app`.
    """
    for grp in in_app.registered_groups:
        if grp.name == name:
            return grp.typer_instance
    return None

def add_command(app: Typer, name: str, cmd: Callable, *, help: str | None=None,
                panel: str | None=None) -> None:
    """Adds a command to a Typer application, potentially creating sub-command groups.

    This function allows adding commands using a dot-separated `name` to specify
    their position within a hierarchy of command groups. If intermediate groups
    do not exist, they are created.

    Arguments:
       app:   The root Typer application or a parent group to which the
              command (or its parent group) will be added.
       name:  The command name. If it contains dots (e.g., "group.subgroup.command"),
              "group" and "subgroup" will be created as Typer groups if they
              don't already exist.
       cmd:   The function to be registered as the Typer command.
       help:  Optional help text for the command. This will be displayed in the `--help` output.
       panel: Optional name of the Rich help panel under which this command should be listed
              in the Typer help output.
    """
    names: list[str] = name.split('.')
    group: Typer = app
    for group_name in names[:-1]:
        sub_group = find_group(group, group_name)
        if sub_group is None:
            # Create a new Typer group if it doesn't exist
            sub_group = Typer(name=group_name)
            group.add_typer(sub_group)
            group = sub_group
        else:
            group = sub_group
    # Add the command to the final (sub)group
    group.command(name=names[-1], help=help, rich_help_panel=panel)(cmd)

def cli_loop(*, restart: bool) -> bool:
    """Sets up and runs the Typer CLI application, handling REPL invocation.

    This function initializes the main Typer application, registers command groups,
    and dynamically loads commands from entry points and recipes. If the CLI is
    invoked without a subcommand, it launches the REPL.

    Arguments:
      restart: If True, indicates that the CLI is being restarted (e.g., after
               a command requested a restart). This can be used to modify
               initial REPL messages.

    Returns:
      True if the REPL (or a command executed within it) requested a restart
      of the CLI loop, False otherwise for a normal termination.
    """
    def replcheck(ctx: Context):
        """Typer callback invoked when no subcommand is specified.

        This function is responsible for initiating the REPL session.
        It prints an introductory message if it's the first REPL invocation
        (not a restart) and then starts the `repl` function.
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

    app: Typer | None = None
    going_repl = len(sys.argv) == 1 # Determine if REPL mode is likely
    if going_repl:
        # For REPL mode, intro is REPL_HELP
        app = Typer(rich_markup_mode="markdown", epilog=REPL_HELP)
    else:
        # For direct command mode, intro is the module docstring
        app = Typer(rich_markup_mode="markdown", help=__doc__, context_settings={"help_option_names": ["-h", "--help"]})
    # Store internal state flags on the app object
    app._in_repl = False
    app._restart = restart
    # Register the replcheck callback
    app.callback(invoke_without_command=True)(replcheck)
    # Install command groups
    for group_name, group_help in command_groups:
        app.add_typer(Typer(), name=group_name, help=group_help)
    # Install registered commands from entry points
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
    # Install commands from registered recipes
    recipe: RecipeInfo
    for recipe in recipe_registry.values():
        if recipe.application is None:
            try:
                add_command(app, f'run.{recipe.name}', run_recipe,
                            help=recipe.description)
            except Exception as exc:
                console.print_error(f"Cannot install command '{recipe.name}'\n{exc!s}")
        else:
            application: ApplicationInfo = application_registry.get(recipe.application.uid)
            if application is None:
                console.print_error(f"Cannot install recipe {recipe.name} due to missing application.")
                continue
            try:
                add_command(app, f'run.{recipe.name}', application.cli_command_obj,
                            help=get_first_line(recipe.description))
            except Exception as exc:
                console.print_error(f"Cannot install command '{recipe.name}'\n{exc!s}")
    # Install commands for applications that do not use recipes
    app_info: ApplicationInfo
    for app_info in application_registry.values():
        if app_info.recipe_factory is None:
            add_command(app, f'run.{app_info.get_recipe_name()}', app_info.cli_command_obj,
                        help=get_first_line(app_info.description))
    # Execute the Typer application
    try:
        app(standalone_mode=False) # standalone_mode=False is important for REPL to work correctly with exceptions
    except Exception as exc:
        console.print_error(exc)
        if os.getenv('SATURNIN_DEBUG') is not None:
            console.print_exception()
    return app._restart # Return the restart flag determined by the REPL or commands

def main():
    """Main entry point for the Saturnin CLI.

    This function manages the `.cli_loop`, allowing for restarts if requested
    by a command or the REPL itself (e.g., after installing new packages
    that might add new commands).
    """
    restart = False
    while restart := cli_loop(restart=restart):
        pass

if __name__ == '__main__':
    main()

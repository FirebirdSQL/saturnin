#coding:utf-8
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

"""Saturnin CLI manager script


"""

# Commands
# LIST - print list of items (services, nodes, packages etc.)
# SHOW - print details about particular item
# EDIT - Edit items (configuration etc.)
# CREATE - create item
# RUN - run components
# START - ??
# STOP - ??

from __future__ import annotations
from typing import Callable, List
from typer import Typer, Context
from saturnin.base import site
from saturnin.component.registry import iter_entry_points
from .repl import repl, IOManager

app = Typer(rich_markup_mode="rich", help="Saturnin management utility.")
app.add_typer(Typer(), name='list', help="Print list of items (services, nodes, packages etc.)")
app.add_typer(Typer(), name='show', help="Print details about particular item (service, node, package etc.)")
app.add_typer(Typer(), name='edit', help="Edit item (configuration, recipe etc.)")
app.add_typer(Typer(), name='create', help="Create item (configuration, recipe etc.)")
app.add_typer(Typer(), name='run', help="Run Saturnin components (services, applications, utilities etc.)")
app.add_typer(Typer(), name='update', help="Update items (components, OIDs etc.)")

app._in_repl = False

@app.callback(invoke_without_command=True)
def _check(ctx: Context):
    """This method start REPL when CLI is started without subsommand.
    """
    if not app._in_repl and ctx.invoked_subcommand is None:
        app._in_repl = True
        site.print(f"{ctx.command.help}\n\nType '?' or '?<command>' for help.\nType 'quit' to leave the console.")
        with IOManager(ctx) as ioman:
            repl(ctx, ioman)


def find_group(app: Typer, name: str) -> Typer:
    "Returns sub-command group in command group."
    for grp in app.registered_groups:
        if grp.name == name:
            return grp.typer_instance
    return None

def add_command(name: str, cmd: Callable) -> None:
    """Add command into main Typer application.

    Arguments:
       name: Command name. Can use dot notation to create a sub-command.
       cmd:  Callable to be registered as Typer command.
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
    group.command(name=names[-1])(cmd)

def load_commands() -> None:
    """Load registered saturnin CLI commands.
    """
    for entry in iter_entry_points('saturnin.commands'):
        add_command(entry.name, entry.load())

def main():
    """Saturnin CLI manager.
    """
    load_commands()
    app()

if __name__ == '__main__':
    main()

#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/command.py
# DESCRIPTION:    Base classes for Saturnin CLI commands
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

"""Saturnin base classes for CLI commands


"""

from __future__ import annotations
from typing import Dict
from weakref import proxy
from argparse import ArgumentParser, Namespace
from traceback import format_exception_only
from pkg_resources import iter_entry_points
from firebird.base.signal import eventsocket
from saturnin.base import Error

class Command:
    """Base class for Saturnin CLI commands.
    """
    def __init__(self, name: str, description: str):
        self.name: str = name
        self.description: str = description
    def print_table(self, headers: List[str], data: List[List[str]]) -> None:
        """Print table.
        """
        sizes = [len(i) for i in headers]
        for row in data:
            for i, col in zip(range(len(sizes)), row):
                sizes[i] = max(sizes[i], len(col))
        fmt = ' '.join(f'{{!s:{size}}}' for size in sizes)
        fmt += '\n'
        self.out(fmt.format(*headers))
        self.out(fmt.format(*['-' * size for size in sizes]))
        for row in data:
            self.out(fmt.format(*row))
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set CLI arguments.
        """
    def on_error(self, exc: Exception):
        """Called when exception is raised in `.run()`.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
    @eventsocket
    def out(self, msg: str, end='') -> None:
        """Print informational message.
        """


class HelpCommand(Command):
    """Show help for commands.
    """
    def __init__(self):
        super().__init__('help', "Show help for commands.")
        self.parser: ArgumentParser = None
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
        self.manager = proxy(manager)
        parser.add_argument('command')
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        self.manager.parser.parse_args([args.command, '--help'])

class CommandManager:
    """Saturni CLI command manager.
    """
    def __init__(self, parser: ArgumentParser):
        """
        Arguments:
            parser: Argument parser.
        """
        self.commands: Dict[str, Command]= {}
        self.parser: ArgumentParser = parser
        self.subparsers = \
            self.parser.add_subparsers(metavar='', prog=f'\n  {parser.prog}', required=True)
        self.parser._subparsers.title = 'Commands'
    def register_command(self, cmd: Command) -> None:
        """Registers command.

        Arguments:
            cmd: Command to be registered.

        Raises:
            Error: If command is already registered.
        """
        if cmd.name in self.commands:
            raise Error(f"Command {cmd.name} already registered")
        self.commands[cmd.name] = cmd
        cmd_parser = self.subparsers.add_parser(cmd.name, description=cmd.description,
                                                help=cmd.description)
        cmd.set_arguments(self, cmd_parser)
        cmd.out = self.out
        cmd_parser.set_defaults(runner=cmd.run)
        cmd_parser.set_defaults(err_handler=cmd.on_error)
    def out(self, msg: str, end='') -> None:
        """Print message to stdout.
        """
        print(msg, end=end, flush=True)
    def load_commands(self, group: str) -> List[Command]:
        """Load commands registered in `options.entry_point` section of `setup.cfg` file.

        Arguments:
            group: Entry-point group name.

        Example:
            ::

               # setup.cfg:

               [options.entry_points]
               saturnin.commands =
                   saturnin.config = saturnin.platform.commands.config:ConfigCommand
                   saturnin.runner = saturnin.platform.commands.run:RunCommand

               # will be loaded with:

               load_commands('saturnin.commands')
        """
        for cmd in (entry.load() for entry in iter_entry_points(group)):
            self.register_command(cmd())
    def run(self, args=None) -> None:
        """Process arguments and execute selected command.
        """
        args = self.parser.parse_args()
        try:
            args.runner(args)
        except Exception as exc:
            try:
                args.err_handler(exc)
            except:
                pass
            msg = ''.join(format_exception_only(type(exc), exc))
            _, msg = msg.split(': ', 1)
            self.parser.exit(1, msg)


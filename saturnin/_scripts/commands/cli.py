#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/cli.py
# DESCRIPTION:    Saturnin console commands
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

"""Saturnin console commands


"""

from __future__ import annotations
from typing import Dict
from argparse import ArgumentParser, Namespace
from saturnin.base import Error
from saturnin.lib.command import Command, CommandManager

class StartCommand(Command):
    """START Saturnin console command.

    Starts Saturnin node or service.
    """
    def __init__(self):
        super().__init__('start', "Start Saturnin node or service")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        print(f"Running {self.name}")

class StopCommand(Command):
    """STOP Saturnin console command.

    Stops Saturnin node or service.
    """
    def __init__(self):
        super().__init__('stop', "Stop Saturnin node or service")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        print(f"Running {self.name}")

class ListCommand(Command):
    """LIST Saturnin console command.

    Lists runing nodes and services.
    """
    def __init__(self):
        super().__init__('list', "List runing nodes and services")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        print(f"Running {self.name}")


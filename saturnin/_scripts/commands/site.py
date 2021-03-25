#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/site.py
# DESCRIPTION:    Saturnin site manager commands
# CREATED:        11.3.2021
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

"""saturnin - Saturnin site manager commands


"""

from __future__ import annotations
from typing import Dict, List, Optional
from pathlib import Path
from argparse import ArgumentParser, Namespace
from configparser import ConfigParser, ExtendedInterpolation
from saturnin.base.site import site, CONFIG_HDR
from saturnin.lib.command import Command, CommandManager

class InitCommand(Command):
    """INIT Saturnin site manager command.

    Initializes saturnin site.
    """
    def __init__(self):
        super().__init__('init', "Initialize Saturnin site")
    def init_directories(self, args: Namespace) -> None:
        ""
        def ensure_dir(name: str, path: Path):
            self.out(f"{name}: {path} ... ")
            if not path.exists():
                path.mkdir(parents=True)
            self.out("OK\n")

        self.out('Creating Saturnin directories...\n')
        if site.scheme.has_home_env():
            print(f"  SATURNIN_HOME is set to     : {site.scheme.home}")
        else:
            print("  SATURNIN_HOME env. variable not defined")
        ensure_dir("  Saturnin configuration      ", site.scheme.config)
        ensure_dir("  Saturnin data               ", site.scheme.data)
        ensure_dir("  Run-time data               ", site.scheme.run_data)
        ensure_dir("  Log files                   ", site.scheme.logs)
        ensure_dir("  Temporary files             ", site.scheme.tmp)
        ensure_dir("  Cache                       ", site.scheme.cache)
        ensure_dir("  User-specific configuration ", site.scheme.user_config)
        ensure_dir("  User-specific data          ", site.scheme.user_data)
        ensure_dir("  PID files                   ", site.scheme.pids)
    def create_config_files(self, args: Namespace) -> None:
        ""
        def ensure_config(path: Path, content: str):
            if path.is_file():
                if not args.new_config:
                    self.out(f"  {path} already exists.\n")
                    return
                path.replace(path.with_suffix(path.suffix + '.bak'))
            self.out(f"  Writing : {path} ... ")
            path.write_text(content)
            self.out("OK\n")

        self.out("Creating configuration files...\n")
        cfg = CONFIG_HDR + site.config.get_config()
        ensure_config(site.scheme.site_conf, cfg)
        ensure_config(site.scheme.user_conf, cfg)
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
        parser.add_argument('--new-config', action='store_true', default=False,
                            help="Creates configuration files even if they exists")
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        self.init_directories(args)
        self.create_config_files(args)

class CreateCommand(Command):
    """CREATE Saturnin site manager command.

    Create recipes, configurations and other site items.
    """
    def __init__(self):
        super().__init__('create', "Create recipes, configurations and other site items")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        print(f"Running {self.name}")

class EditCommand(Command):
    """EDIT Saturnin site manager command.

    Edit recipes, configurations and other site items.
    """
    def __init__(self):
        super().__init__('edit', "Edit recipes, configurations and other site items")
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
    """LIST Saturnin site manager command.

    Lists information about Saturnin site.
    """
    def __init__(self):
        super().__init__('list', "List information about Saturnin site")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        self.out('Saturnin directories...\n')
        if site.scheme.has_home_env():
            self.out(f"  SATURNIN_HOME is set to     : {site.scheme.home}\n")
        else:
            self.out("  SATURNIN_HOME env. variable not defined\n")
        self.out(f"  Saturnin configuration      : {site.scheme.config}\n")
        self.out(f"  Saturnin data               : {site.scheme.data}\n")
        self.out(f"  Run-time data               : {site.scheme.run_data}\n")
        self.out(f"  Log files                   : {site.scheme.logs}\n")
        self.out(f"  Temporary files             : {site.scheme.tmp}\n")
        self.out(f"  Cache                       : {site.scheme.cache}\n")
        self.out(f"  User-specific configuration : {site.scheme.user_config}\n")
        self.out(f"  User-specific data          : {site.scheme.user_data}\n")
        self.out(f"  PID files                   : {site.scheme.pids}\n")



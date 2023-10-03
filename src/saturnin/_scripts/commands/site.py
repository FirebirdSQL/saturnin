# SPDX-FileCopyrightText: 2021-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

"""Saturnin site manager commands


"""

from __future__ import annotations
from pathlib import Path
from enum import Enum
import typer
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Confirm
from rich.syntax import Syntax
from saturnin.base import CONFIG_HDR, directory_scheme, saturnin_config, venv
from saturnin.lib.console import console, DEFAULT_THEME, RICH_YES, RICH_NO, RICH_OK
from saturnin._scripts.completers import path_completer

#: Typer command group for site management commands
app = typer.Typer(rich_markup_mode="rich", help="Saturnin site management.")

def ensure_dir(description: str, path: Path):
    """Create directory (incl. parents) if it does not exists.

    Arguments:
      description: Directory description.
      path: Directory path.
    """
    console.print(f"{description}: [path]{path}[/path] ... ", end='')
    if not path.exists():
        path.mkdir(parents=True)
    console.print(RICH_OK)

def ensure_config(path: Path, content: str, new_config: bool):
    """Create configuration file if it does not exists.

    Arguments:
      path: Configuration file.
      content: Content to be written into configuration file.
      new_config: When True, the configuration file is written even if it elready exists,
                  but original file is kept as renamed with '.bak' suffix.
    """
    if path.is_file():
        if not new_config:
            console.print(f"  Info : [path]{path}[/path] already exists.")
            return
        path.replace(path.with_suffix(path.suffix + '.bak'))
    console.print(f"  Writing : [path]{path}[/path] ... ", end='')
    path.write_text(content)
    console.print(RICH_OK)

def add_path(table: Table, description: str, path: Path) -> None:
    """Adds new row to table with information about path incl. indicator whether path exists.

    Arguments:
      table: Rich table
      description: Path description
      path: Path
    """
    table.add_row(description, RICH_YES if path.exists() else RICH_NO, str(path))


@app.command()
def create_home() -> None:
    """Creates Saturnin home directory in Saturnin virtual environment.

    ---

    #### Important:

    To have desired effect, this command must be executed BEFORE **initialize**.
    """
    ensure_dir('Saturnin HOME', venv() / 'home')

@app.command()
def initialize(new_config: bool= \
                 typer.Option(False, '--new-config',
                              help="Create configuration files even if they already exist."),
               yes: bool= \
                 typer.Option(False, '--yes',
                              help="Don’t ask for confirmation of site initialization.")) -> None:
    """Initialize Saturnin environment/installation.

    ---

    It creates required directories and configuration files.

    #### Important:

    Before you execute this command, consider where you want to place numerous Saturnin
    directories. By default, Saturnin uses directory scheme according to platform standards.

    * If you want to place main directories under central home directory, set **SATURNIN_HOME**
      environment variable to point to this directory.

    * If you want to place home directory in Saturnin virtual environment, first execute
      the **create home** command.

    """
    if not yes:
        yes = Confirm.ask("Are you sure you want to initialize the Saturnin environment?")
    if yes:
        saturnin_cfg = CONFIG_HDR + saturnin_config.get_config()
        steps = [(console.print, ['Ensuring existence of Saturnin directories...']),
                 (ensure_dir, ["  Saturnin configuration      ", directory_scheme.config]),
                 (ensure_dir, ["  Saturnin data               ", directory_scheme.data]) ,
                 (ensure_dir, ["  Run-time data               ", directory_scheme.run_data]) ,
                 (ensure_dir, ["  Log files                   ", directory_scheme.logs]) ,
                 (ensure_dir, ["  Temporary files             ", directory_scheme.tmp]) ,
                 (ensure_dir, ["  Cache                       ", directory_scheme.cache]) ,
                 (ensure_dir, ["  User-specific configuration ", directory_scheme.user_config]) ,
                 (ensure_dir, ["  User-specific data          ", directory_scheme.user_data]) ,
                 (ensure_dir, ["  PID files                   ", directory_scheme.pids]) ,
                 (ensure_dir, ["  Recipes                     ", directory_scheme.recipes]) ,
                 (console.print, ['Creating configuration files...']),
                 (ensure_config, [directory_scheme.site_conf, saturnin_cfg, new_config]) ,
                 (ensure_config, [directory_scheme.user_conf, saturnin_cfg, new_config]) ,
                 (ensure_config, [directory_scheme.theme_file, DEFAULT_THEME.config, new_config]) ,
                 ]
        for func, params in steps:
            func(*params)

@app.command()
def list_directories() -> None:
    """List Saturnin directories.
    Emojis: :heavy_check_mark: :heavy_multiplication_x:
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white')
    tbl.add_column(width=1)
    tbl.add_column(style='path')
    if directory_scheme.has_home_env():
        tbl.add_row('[bold]SATURNIN_HOME[/bold] is set to', ':', str(directory_scheme.home))
    else:
        tbl.add_row('[important]SATURNIN_HOME env. variable not defined', '', '')
    add_path(tbl, 'Saturnin configuration', directory_scheme.config)
    add_path(tbl, 'Saturnin data', directory_scheme.data)
    add_path(tbl, 'Run-time data', directory_scheme.run_data)
    add_path(tbl, 'Log files', directory_scheme.logs)
    add_path(tbl, 'Temporary files', directory_scheme.tmp)
    add_path(tbl, 'Cache', directory_scheme.cache)
    add_path(tbl, 'User-specific configuration', directory_scheme.user_config)
    add_path(tbl, 'User-specific data', directory_scheme.user_data)
    add_path(tbl, 'PID files', directory_scheme.pids)
    add_path(tbl, 'Recipes', directory_scheme.recipes)
    console.print(Panel(tbl, title='[title]Saturnin directories',
                        title_align='left', box=box.ROUNDED))

@app.command()
def list_configs() -> None:
    """List Saturnin configuration files.
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white')
    tbl.add_column(width=1)
    tbl.add_column(style='path')
    add_path(tbl, 'Main configuration', directory_scheme.site_conf)
    add_path(tbl, 'User configuration', directory_scheme.user_conf)
    add_path(tbl, 'Console theme', directory_scheme.theme_file)
    add_path(tbl, 'Firebird configuration', directory_scheme.firebird_conf)
    add_path(tbl, 'Logging configuration', directory_scheme.logging_conf)
    console.print(Panel(tbl, title='[title]Configuration files', title_align='left',
                        box=box.ROUNDED))

@app.command()
def list_datafiles() -> None:
    """List Saturnin data files.
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white')
    tbl.add_column(width=1)
    tbl.add_column(style='path')
    add_path(tbl, 'Installed services', directory_scheme.site_services_toml)
    add_path(tbl, 'Installed applications', directory_scheme.site_apps_toml)
    add_path(tbl, 'Registered OIDs', directory_scheme.site_oids_toml)
    add_path(tbl, 'Console history', directory_scheme.history_file)
    add_path(tbl, 'Default log file', directory_scheme.log_file)
    console.print(Panel(tbl, title='[title]Saturnin data files', title_align='left',
                        box=box.ROUNDED))

class _Configs(Enum):
    "Saturnin configuration files"
    MAIN = 'main'
    USER = 'user'
    FIREBIRD = 'firebird'
    LOGGING = 'logging'
    THEME = 'theme'
    @property
    def path(self) -> Path:
        "Path to configuration file."
        if self is _Configs.MAIN:
            return directory_scheme.site_conf
        if self is _Configs.USER:
            return directory_scheme.user_conf
        if self is _Configs.FIREBIRD:
            return directory_scheme.firebird_conf
        if self is _Configs.LOGGING:
            return directory_scheme.logging_conf
        return directory_scheme.theme_file


@app.command()
def show_config(config_file: _Configs = typer.Argument(..., help="Configuration file")):
    """Show content of configuration file.
    """
    lexer = config_file.path.suffix[1:]
    if lexer == 'conf':
        lexer = 'cfg'
    console.print(Syntax(config_file.path.read_text(), lexer))

@app.command()
def edit_config(config_file: _Configs = typer.Argument(..., help="Configuration file",
                                                   autocompletion=path_completer)):
    """Edit configuration file.
    """
    edited = typer.edit(config_file.path.read_text(), saturnin_config.editor.value,
                        extension=config_file.path.suffix)
    if edited is not None:
        config_file.path.write_text(edited)
        console.print("Configuration updated.")

@app.command()
def create_config(config_file: _Configs= \
                    typer.Argument(..., help="Configuration file to be created"),
                  new_config: bool= \
                    typer.Option(False, '--new-config',
                                 help="Create configuration file even if it already exist.")):
    """Creates configuration file with default content.
    """
    config: str = None
    if config_file in (_Configs.MAIN, _Configs.USER):
        config = CONFIG_HDR + saturnin_config.get_config()
    elif config_file is _Configs.THEME:
        config = DEFAULT_THEME.config
    elif config_file is _Configs.FIREBIRD:
        try:
            from firebird.driver import driver_config # pylint: disable=C0415
            srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
            driver_config.register_server('local', srv_cfg)
            config = driver_config.get_config()
        except Exception: # pylint: disable=W0703
            console.print_error("Firebird driver not installed.")
            return None
    elif config_file is _Configs.LOGGING:
        config = f"""
; =====================
; Logging configuration
; =====================
;
; For details see https://docs.python.org/3/howto/logging.html#configuring-logging and
; https://docs.python.org/3/library/logging.config.html#logging-config-fileformat

[loggers]
keys = root, saturnin, trace

[handlers]
keys = file, trace, stderr

[formatters]
keys = simple, context

[logger_root]
handlers = stderr

[logger_saturnin]
handlers = file
qualname=saturnin

[logger_trace]
handlers = trace
qualname=trace
level=DEBUG
propagate=0

[handler_file]
; This handler sends logging output to file in log directory
class = FileHandler
args = ('{directory_scheme.log_file}', 'w')
formatter=context

[handler_stderr]
; This handler sends logging output to STDERR
class = StreamHandler
args = (sys.stderr,)
formatter=simple

[handler_trace]
; This handler sends logging output to STDERR
class = StreamHandler
args = (sys.stderr,)
formatter=context

[formatter_simple]
format = %(asctime)s %(levelname)s [%(process)s/%(thread)s] %(message)s

[formatter_context]
format = %(asctime)s %(levelname)s [%(processName)s/%(threadName)s] [%(agent)s:%(context)s] %(message)s
"""
    ensure_config(config_file.path, config, new_config)
    return None

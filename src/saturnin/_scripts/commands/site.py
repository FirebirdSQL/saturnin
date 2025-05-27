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

"""Saturnin site management commands.

This module provides Typer commands for initializing and managing the
Saturnin site environment, including directory creation, configuration file
handling, and listing site-specific paths.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from saturnin._scripts.completers import path_completer
from saturnin.base import CONFIG_HDR, directory_scheme, saturnin_config, venv
from saturnin.lib.console import DEFAULT_THEME, RICH_NO, RICH_OK, RICH_YES, console

#: Typer command group for site management commands.
app = typer.Typer(rich_markup_mode="rich", help="Saturnin site management.")

def ensure_dir(description: str, path: Path):
    """Ensures a directory exists, creating it (and any parents) if necessary.

    Prints a status message to the console indicating the action taken.

    Arguments:
      description: A description of the directory's purpose (for console output).
      path: The `Path` object representing the directory to ensure.
    """
    console.print(f"{description}: [path]{path}[/path] ... ", end='')
    if not path.exists():
        path.mkdir(parents=True)
        console.print(RICH_OK) # Indicate creation
    else:
        console.print(RICH_YES) # Indicate already exists

def ensure_config(path: Path, content: str, new_config: bool): #noqa : FBT001
    """Creates or updates a configuration file with the given content.

    Prints status messages to the console. If `new_config` is True and the
    file exists, the original is backed up with a '.bak' suffix before writing.

    Arguments:
      path: The `Path` object for the configuration file.
      content: The string content to write to the file.
      new_config: If True, overwrite an existing file (backing it up).
                         If False, do nothing if the file already exists.
    """
    if path.is_file():
        if not new_config:
            console.print(f"  Info : [path]{path}[/path] already exists.")
            return
        backup_path = path.with_suffix(path.suffix + '.bak')
        console.print(f"  Backing up existing file to: [path]{backup_path}[/path] ... ", end='')
        path.replace(backup_path)
        console.print(RICH_OK)
    console.print(f"  Writing : [path]{path}[/path] ... ", end='')
    path.write_text(content)
    console.print(RICH_OK)

def add_path(table: Table, description: str, path: Path) -> None:
    """Adds a row to a Rich Table displaying a path and its existence status.

    The row includes the description, an indicator (✔/✖) of whether the
    path exists, and the string representation of the path.

    Arguments:
      table: The Rich `Table` instance to which the row will be added.
      description: A textual description of the path.
      path: The `Path` object to display and check for existence.
    """
    table.add_row(description, RICH_YES if path.exists() else RICH_NO, str(path))


@app.command()
def create_home() -> None:
    """Creates the Saturnin 'home' subdirectory within the active virtual environment.

    This command is typically used to establish a conventional location for Saturnin's
    site-specific files when `SATURNIN_HOME` is not explicitly set and the
    virtual environment structure is preferred.

    ### Important:

    To have the intended effect on the directory scheme used by `initialize`,
    this command should be executed **before** the `initialize` command.
    """
    if directory_scheme.has_home_env():
        console.print_error("The home directory is already defined by SATURNIN_HOME environment variable.")
        raise typer.Exit(code=1)
    if not venv():
        console.print_error("This command is intended for use within a Saturnin virtual environment.")
        console.print_error("Virtual environment not detected.")
        raise typer.Exit(code=1)
    ensure_dir('Saturnin HOME', venv() / 'home')

@app.command()
def initialize(*,
    new_config: Annotated[bool,
       typer.Option('--new-config', help="Create configuration files even if they already exist.")]=False,
    yes: Annotated[bool,
       typer.Option('--yes', help="Don't ask for confirmation of site initialization.")]=False
    ) -> None:
    """Initializes the Saturnin environment and directory structure.

    This command creates all standard directories required by Saturnin (for configuration,
    data, logs, etc.) and generates default configuration files (e.g., `saturnin.conf`,
    `theme.conf`).

    #### Important Considerations:

    Before running `initialize`, determine where Saturnin's directories should reside:

    *   **Central Home Directory**: If you want all Saturnin directories to be
    located under a specific central path, set the `SATURNIN_HOME`
    environment variable to this path *before* running `initialize`.

    *   **Virtual Environment Home**: If you prefer to keep Saturnin's home
    directory within its virtual environment, first execute the
    `create home` command, then run `initialize`.

    *   **Platform Defaults**: If neither `SATURNIN_HOME` is set nor `create home`
    has been used to create a venv-local home, Saturnin will use
    platform-specific default locations for its directories.

    ---

    Using the `--new-config` option will cause existing configuration files to be
    renamed with a `.bak` extension before new default files are written.
    """
    if not yes:
        home = 'Not set (using platform defaults)' if not directory_scheme.has_home_env() else str(directory_scheme.home)
        console.print(Panel(Markdown(
            "This command will create Saturnin's standard directories and "
            "default configuration files based on the current environment settings "
            f"(see `saturnin list directories` for current paths).\n\n"
            f"Current `SATURNIN_HOME`: `{home}`"
        ), title="[warning]Confirmation Required[/warning]", border_style="warning"))
        proceed = Confirm.ask("Are you sure you want to initialize the Saturnin environment?", default=False)
        if not proceed:
            console.print("Initialization cancelled by user.")
            return

    saturnin_cfg_content = CONFIG_HDR + saturnin_config.get_config()
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
             (console.print, ['\nCreating configuration files...']),
             (ensure_config, [directory_scheme.site_conf, saturnin_cfg_content, new_config]) ,
             (ensure_config, [directory_scheme.user_conf, saturnin_cfg_content, new_config]) ,
             (ensure_config, [directory_scheme.theme_file, DEFAULT_THEME.config, new_config]) ,
             ]
    for func, params in steps:
        func(*params)
    console.print("\n[info]Saturnin environment initialized successfully.[/info]")

@app.command()
def list_directories() -> None:
    """Lists the key directories used by Saturnin and indicates their existence.
    Emojis: :heavy_check_mark: (exists) / :heavy_multiplication_x: (does not exist)
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white') # Description
    tbl.add_column(width=1) # Exists icon
    tbl.add_column(style='path') # Path
    if directory_scheme.has_home_env():
        tbl.add_row('[bold]SATURNIN_HOME[/bold] is set to', ':', str(directory_scheme.home))
    else:
        tbl.add_row('[important]SATURNIN_HOME env. variable not defined', '-',
                    '(Using platform defaults or venv if `home` subdir exists)')
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
                        title_align='left', box=box.ROUNDED, padding=(1,2)))

@app.command()
def list_configs() -> None:
    """Lists Saturnin's main configuration files and indicates their existence.
    Emojis: :heavy_check_mark: (exists) / :heavy_multiplication_x: (does not exist)
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white') # Description
    tbl.add_column(width=1) # Exists icon
    tbl.add_column(style='path') # Path
    add_path(tbl, 'Main configuration', directory_scheme.site_conf)
    add_path(tbl, 'User configuration', directory_scheme.user_conf)
    add_path(tbl, 'Console theme', directory_scheme.theme_file)
    add_path(tbl, 'Firebird configuration', directory_scheme.firebird_conf)
    add_path(tbl, 'Logging configuration', directory_scheme.logging_conf)
    console.print(Panel(tbl, title='[title]Configuration files', title_align='left',
                        box=box.ROUNDED, padding=(1,2)))

@app.command()
def list_datafiles() -> None:
    """Lists Saturnin's key data files and indicates their existence.
    Emojis: :heavy_check_mark: (exists) / :heavy_multiplication_x: (does not exist)
    """
    tbl = Table.grid(padding=(0, 1, 0, 1))
    tbl.add_column(style='white') # Description
    tbl.add_column(width=1) # Exists icon
    tbl.add_column(style='path') # Path
    add_path(tbl, 'Installed services', directory_scheme.site_services_toml)
    add_path(tbl, 'Installed applications', directory_scheme.site_apps_toml)
    add_path(tbl, 'Registered OIDs', directory_scheme.site_oids_toml)
    add_path(tbl, 'Console history', directory_scheme.history_file)
    add_path(tbl, 'Default log file', directory_scheme.log_file)
    console.print(Panel(tbl, title='[title]Saturnin data files', title_align='left',
                        box=box.ROUNDED, padding=(1,2)))

class _Configs(Enum):
    """Enumeration of manageable Saturnin configuration files."""
    MAIN = 'main'
    USER = 'user'
    FIREBIRD = 'firebird'
    LOGGING = 'logging'
    THEME = 'theme'
    @property
    def path(self) -> Path:
        """Returns the `Path` object for the selected configuration file type."""
        if self is _Configs.MAIN:
            return directory_scheme.site_conf
        if self is _Configs.USER:
            return directory_scheme.user_conf
        if self is _Configs.FIREBIRD:
            return directory_scheme.firebird_conf
        if self is _Configs.LOGGING:
            return directory_scheme.logging_conf
        # Default to theme if not matched
        return directory_scheme.theme_file


@app.command()
def show_config(config_file: Annotated[_Configs, typer.Argument(help="Configuration file")]):
    """Displays the content of a specified Saturnin configuration file.

    The content is shown with syntax highlighting appropriate for the file type
    (e.g., '.conf' files are highlighted as INI/CFG).
    """
    target_path = config_file.path
    if not target_path.is_file():
        console.print_error(f"Configuration file '[path]{target_path}[/path]' does not exist.")
        return
    lexer = target_path.suffix[1:]
    if lexer == 'conf':
        lexer = 'ini' # More common lexer name for .conf files
    elif lexer == 'toml':
        lexer = 'toml'
    else:
        lexer = 'text' # Fallback lexer
    console.print(Syntax(target_path.read_text(encoding='utf-8'), lexer, line_numbers=True, word_wrap=True))

@app.command()
def edit_config(
    config_file: Annotated[_Configs, typer.Argument(help="Configuration file",
                                                    autocompletion=path_completer)]
    ):
    """Opens the specified Saturnin configuration file in an external editor.

    The editor used is determined by the `EDITOR` environment variable or Saturnin's
    configured default editor. If changes are saved, the file is updated.
    """
    target_path = config_file.path
    if not target_path.is_file():
        # Offer to create it if it's a known config type that can be created
        if Confirm.ask(f"Configuration file '[path]{target_path}[/path]' does not exist. Create it with default content?"):
            create_config(config_file=config_file, new_config=False) # Call create_config to generate it
            if not target_path.is_file(): # If creation failed or was skipped
                console.print_error("File still does not exist. Aborting edit.")
                return
        else:
            console.print("Edit cancelled.")
            return

    editor_to_use = saturnin_config.editor.value or os.getenv('EDITOR')
    if not editor_to_use:
        console.print_error("No editor configured. Set the EDITOR environment variable or the 'editor' option in saturnin.conf.")
        return
    try:
        edited_content = typer.edit(target_path.read_text(encoding='utf-8'), editor=editor_to_use,
                                extension=target_path.suffix)
    except Exception as exc:
        console.print_error(exc)
        return
    if edited_content is not None:
        target_path.write_text(edited_content, encoding='utf-8')
        console.print(f"Configuration file '[path]{target_path}[/path]' updated.")
    else:
        console.print("Edit cancelled or no changes made.")

@app.command()
def create_config(
    config_file: Annotated[_Configs, typer.Argument(help="Configuration file to be created")],
    *,
    new_config: Annotated[bool, typer.Option('--new-config',
        help="Create configuration file even if it already exists (existing file will be backed up).")]=False
    ):
    """Creates a specified Saturnin configuration file with its default content.

    If the file already exists, it will only be overwritten if `--new-config` is used
    (in which case the original is backed up).
    """
    config: str | None = None
    target_path = config_file.path
    if config_file in (_Configs.MAIN, _Configs.USER):
        config = CONFIG_HDR + saturnin_config.get_config()
    elif config_file is _Configs.THEME:
        config = DEFAULT_THEME.config
    elif config_file is _Configs.FIREBIRD:
        try:
            from firebird.driver import driver_config
            srv_cfg = """[local]
host = localhost
user = SYSDBA
password = masterkey
"""
            driver_config.register_server('local', srv_cfg)
            config = driver_config.get_config()
        except ImportError:
            console.print_error("Firebird driver package not installed. Cannot create default firebird.conf.")
            console.print_error("Please install 'firebird-driver' or create the file manually.")
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
    ensure_config(config_file.path, config, new_config=new_config)
    return None

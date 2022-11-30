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

"""Saturnin site manager commands


"""

from __future__ import annotations
from pathlib import Path
import typer
from rich.panel import Panel
from rich import box
from rich.prompt import Confirm
from saturnin.base._site import site, CONFIG_HDR

app = typer.Typer(rich_markup_mode="rich", help="Saturnin site management.")

def ensure_dir(description: str, path: Path):
    """Create directory (incl. parents) if it does not exists.

    Arguments:
      description: Directory description.
      path: Directory path.
    """
    site.print(f"{description}: [path]{path}[/path] ... ", end='')
    if not path.exists():
        path.mkdir(parents=True)
    site.print("OK")

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
            site.print(f"  [path]{path}[/path] already exists.")
            return
        path.replace(path.with_suffix(path.suffix + '.bak'))
    site.print(f"  Writing : [path]{path}[/path] ... ", end='')
    path.write_text(content)
    site.print("OK")

@app.command()
def initialize(new_config: bool=typer.Option(False, help="Create configuration files even if they already exist"),
               yes: bool = typer.Option(False, '--yes', help="Don’t ask for confirmation of site initialization")) -> None:
    """Initialize Saturnin environment (installation).

    It creates required directories and configuration files.
    """
    if not yes:
        yes = Confirm.ask("Are you sure you want to initialize the Saturnin environment?")
    saturnin_cfg = CONFIG_HDR + site.config.get_config()
    steps = [(site.print, ['Ensuring existence of Saturnin directories...']),
             (ensure_dir, ["  Saturnin configuration      ", site.scheme.config]),
             (ensure_dir, ["  Saturnin data               ", site.scheme.data]) ,
             (ensure_dir, ["  Run-time data               ", site.scheme.run_data]) ,
             (ensure_dir, ["  Log files                   ", site.scheme.logs]) ,
             (ensure_dir, ["  Temporary files             ", site.scheme.tmp]) ,
             (ensure_dir, ["  Cache                       ", site.scheme.cache]) ,
             (ensure_dir, ["  User-specific configuration ", site.scheme.user_config]) ,
             (ensure_dir, ["  User-specific data          ", site.scheme.user_data]) ,
             (ensure_dir, ["  PID files                   ", site.scheme.pids]) ,
             (site.print, ['Creating configuration files...']),
             (ensure_config, [site.scheme.site_conf, saturnin_cfg, new_config]) ,
             (ensure_config, [site.scheme.user_conf, saturnin_cfg, new_config]) ,
             ]
    for func, params in steps:
        func(*params)

@app.command('directories')
def list_directories() -> None:
    """List Saturnin directories.
    """
    if site.scheme.has_home_env():
        text = f"  [bold]SATURNIN_HOME[/bold] is set to     : [path]{site.scheme.home}[/path]"
    else:
        text = "  [important]SATURNIN_HOME env. variable not defined"
    text += f"""
  Saturnin configuration      : [path]{site.scheme.config}[/path]
  Saturnin data               : [path]{site.scheme.data}[/path]
  Run-time data               : [path]{site.scheme.run_data}[/path]
  Log files                   : [path]{site.scheme.logs}[/path]
  Temporary files             : [path]{site.scheme.tmp}[/path]
  Cache                       : [path]{site.scheme.cache}[/path]
  User-specific configuration : [path]{site.scheme.user_config}[/path]
  User-specific data          : [path]{site.scheme.user_data}[/path]
  PID files                   : [path]{site.scheme.pids}[/path]"""
    site.print(Panel(text, title='[title]Saturnin directories', title_align='left', box=box.ROUNDED))

@app.command('configs')
def list_configs() -> None:
    """List Saturnin configuration files.
    """
    text = f"""  Main configuration     : [path]{site.scheme.site_conf}[/path]
  User configuration     : [path]{site.scheme.user_conf}[/path]
  Firebird configuration : [path]{site.scheme.firebird_conf}[/path]
  Logging configuration  : [path]{site.scheme.logging_conf}[/path]"""
    site.print(Panel(text, title='[title]Configuration files', title_align='left', box=box.ROUNDED))

@app.command('data')
def list_data() -> None:
    """List Saturnin data files.
    """
    text = f"""  Installed components   : [path]{site.scheme.site_components_toml}[/path]
  Registered OIDs        : [path]{site.scheme.site_oids_toml}[/path]"""
    site.print(Panel(text, title='[title]Saturnin data files', title_align='left', box=box.ROUNDED))

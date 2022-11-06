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
from pathlib import Path
import typer
from saturnin.base.site import site, CONFIG_HDR

app = typer.Typer(rich_markup_mode="rich", help="Saturnin site management.")

def ensure_dir(description: str, path: Path):
    """Create directory (incl. parents) if it does not exists.

    Arguments:
      description: Directory description.
      path: Directory path.
    """
    site.print(f"{description}: {path} ... ", end='')
    if not path.exists():
        path.mkdir(parents=True)
    site.print("OK\n")

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
            site.print(f"  {path} already exists.")
            return
        path.replace(path.with_suffix(path.suffix + '.bak'))
    site.print(f"  Writing : {path} ... ", end='')
    path.write_text(content)
    site.print("OK")

def init(new_config: bool=typer.Option(False, help="Creates configuration files even if they exists")) -> None:
    """Initialize Saturnin site (installation).
    """
    site.print('Creating Saturnin directories...')
    if site.scheme.has_home_env():
        site.print(f"  SATURNIN_HOME is set to     : {site.scheme.home}")
    else:
        site.print("  SATURNIN_HOME env. variable not defined")
    ensure_dir("  Saturnin configuration      ", site.scheme.config)
    ensure_dir("  Saturnin data               ", site.scheme.data)
    ensure_dir("  Run-time data               ", site.scheme.run_data)
    ensure_dir("  Log files                   ", site.scheme.logs)
    ensure_dir("  Temporary files             ", site.scheme.tmp)
    ensure_dir("  Cache                       ", site.scheme.cache)
    ensure_dir("  User-specific configuration ", site.scheme.user_config)
    ensure_dir("  User-specific data          ", site.scheme.user_data)
    ensure_dir("  PID files                   ", site.scheme.pids)
    #
    site.print("Creating configuration files...")
    cfg = CONFIG_HDR + site.config.get_config()
    ensure_config(site.scheme.site_conf, cfg, new_config)
    ensure_config(site.scheme.user_conf, cfg, new_config)

def show() -> None:
    """Show information about Saturnin site (installation).
    """
    site.print('Saturnin directories...')
    if site.scheme.has_home_env():
        site.print(f"  SATURNIN_HOME is set to     : {site.scheme.home}")
    else:
        site.print("  SATURNIN_HOME env. variable not defined")
    site.print(f"  Saturnin configuration      : {site.scheme.config}")
    site.print(f"  Saturnin data               : {site.scheme.data}")
    site.print(f"  Run-time data               : {site.scheme.run_data}")
    site.print(f"  Log files                   : {site.scheme.logs}")
    site.print(f"  Temporary files             : {site.scheme.tmp}")
    site.print(f"  Cache                       : {site.scheme.cache}")
    site.print(f"  User-specific configuration : {site.scheme.user_config}")
    site.print(f"  User-specific data          : {site.scheme.user_data}")
    site.print(f"  PID files                   : {site.scheme.pids}")

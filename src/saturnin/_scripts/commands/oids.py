#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/oids.py
# DESCRIPTION:    Saturnin OID registey management commands
# CREATED:        23.11.2022
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

"""Saturnin OID registey management commands

"""

from __future__ import annotations
import typer
from rich.table import Table
from rich import box
from firebird.uuid import (registry, ROOT_SPEC, get_specifications, parse_specifications)
from saturnin.base._site import site

app = typer.Typer(rich_markup_mode="rich", help="Saturnin OID management.")

@app.command('oids')
def list_oids(with_name: str=typer.Option('', help="List only OIDs with this string in name")) -> None:
    """List registered OIDs.
    """
    table = Table(title='Registered OIDs' if not with_name else f"Registered OIDs with name containing '{with_name}'",
                  box=box.ROUNDED)
    table.add_column('OID Name', style='green')
    table.add_column('UID', style='white')
    for node in registry.values():
        if with_name in node.full_name:
            table.add_row(*[node.full_name, str(node.uid)])
    site.console.print(table)

@app.command('oids')
def update_oids(url: str=typer.Argument(ROOT_SPEC, help="URL to OID node specification", metavar='URL')):
    """Update OID registry from specification(s).
    """
    site.print("Downloading OID specifications ... ", end='')
    specifications, errors = get_specifications(url)
    if errors:
        site.print('[bold red]ERROR')
        site.print_error("Errors occured during download:")
        for err_url, error in errors:
            site.print_error(f"URL: {err_url}")
            site.print_error(f"error: {error}")
        return
    site.print('[bold yellow]OK')
    site.print("Parsing OID specifications ... ", end='')
    specifications, errors = parse_specifications(specifications)
    if errors:
        site.print('[bold red]ERROR')
        site.print_error("Errors detected while parsing OID specifications:")
        for err_url, error in errors:
            site.print_error(f"URL: {err_url}")
            site.print_error(f"error: {error}")
        return
    site.print('[bold yellow]OK')
    #
    site.print("Updating OID registry ... ", end='')
    try:
        registry.update_from_specifications(specifications)
    except Exception as exc:
        site.print('[bold red]ERROR')
        site.print_error(exc)
    site.print('[bold yellow]OK')
    site.save_oids()

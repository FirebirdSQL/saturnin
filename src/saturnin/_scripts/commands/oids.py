# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/oids.py
# DESCRIPTION:    Saturnin OID registry management commands
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
# Copyright (c) 2022 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin OID registry management commands

"""

from __future__ import annotations
#from typing import List
from uuid import UUID
import typer
from rich.table import Table
from rich.text import Text
from rich import box
from firebird.uuid import (oid_registry, ROOT_SPEC, get_specifications, parse_specifications,
                           Node)
from saturnin.base import directory_scheme
from saturnin.lib.console import console, _h, RICH_OK, RICH_ERROR
from saturnin._scripts.completers import oid_completer

#: Typer command group for OID management commands
app = typer.Typer(rich_markup_mode="rich", help="Saturnin OID management.")

@app.command()
def list_oids(with_name: str=typer.Option('', help="List only OIDs with this string in name"),
              show_oids: bool = typer.Option(False, '--show-oids',
                                             help="Should OIDs instead UUIDs")) -> None:
    """List registered OIDs.
    """
    table = Table(title='Registered OIDs' if not with_name
                  else f"Registered OIDs with name containing '{with_name}'",
                  box=box.ROUNDED)
    table.add_column('OID Name', style='green')
    table.add_column('OID' if show_oids else 'UUID')
    if oid_registry:
        for node in oid_registry.values():
            if with_name in node.full_name:
                if show_oids:
                    table.add_row(*[node.full_name, Text(node.oid, style='number')])
                else:
                    table.add_row(*[node.full_name, Text(str(node.uid), style='uuid')])
        console.print(table)
    else:
        console.print("No OIDs are registered.")

@app.command()
def update_oids(url: str=typer.Argument(ROOT_SPEC, help="URL to OID node specification",
                                        metavar='URL')):
    """Update OID registry from specification(s).
    """
    console.print("Downloading OID specifications ... ", end='')
    specifications, errors = get_specifications(url)
    if errors:
        console.print(RICH_ERROR)
        console.print_error("Errors occured during download:")
        for err_url, error in errors:
            console.print_error(f"URL: {err_url}")
            console.print_error(f"error: {error}")
        return
    console.print(RICH_OK)
    console.print("Parsing OID specifications ... ", end='')
    specifications, errors = parse_specifications(specifications)
    if errors:
        console.print(RICH_ERROR)
        console.print_error("Errors detected while parsing OID specifications:")
        for err_url, error in errors:
            console.print_error(f"URL: {err_url}")
            console.print_error(f"error: {error}")
        return
    console.print(RICH_OK)
    #
    console.print("Updating OID registry ... ", end='')
    try:
        oid_registry.update_from_specifications(specifications)
    except Exception as exc: # pylint: disable=W0703
        console.print(RICH_ERROR)
        console.print_error(exc)
    console.print(RICH_OK)
    directory_scheme.site_oids_toml.write_text(oid_registry.as_toml())

@app.command()
def show_oid(oid: str=typer.Argument('', help="OID name or GUID",
                                     autocompletion=oid_completer)) -> None:
    """Show information about OID.
    """
    uid: UUID = None
    name: str = None
    node: Node = None
    try:
        uid = UUID(oid)
    except Exception: # pylint: disable=W0703
        name = oid

    if uid is not None:
        node = oid_registry.get(uid)
    else:
        node = oid_registry.find(lambda x: x.full_name.startswith(name))
    if node is None:
        console.print_error('OID not registered!')
        return

    table = Table.grid()
    table.add_column(style='green')
    table.add_column()
    table.add_row('OID:', Text(node.oid, style='number'))
    table.add_row('UID:', _h(Text(str(node.uid))))
    table.add_row('Node name:', Text(node.name))
    table.add_row('Full name:', Text(node.full_name))
    table.add_row('Description:', Text(node.description))
    table.add_row('Contact:', Text(node.contact))
    table.add_row('E-mail:', _h(Text(node.email)))
    table.add_row('Site:', _h(Text(node.site)))
    table.add_row('Node spec.:', _h(Text(str(node.node_spec))))
    table.add_row('Node type:', _h(Text(node.node_type.name)))
    table.add_row('Parent spec.: ', _h(Text(str(node.parent_spec))))
    console.print(table)


if directory_scheme.site_oids_toml.is_file():
    oid_registry.update_from_toml(directory_scheme.site_oids_toml.read_text())

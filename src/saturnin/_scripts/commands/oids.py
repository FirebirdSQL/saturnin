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

"""Typer commands for managing Saturnin's Object Identifier (OID) registry.

This includes listing registered OIDs, updating the registry from remote
specifications, and displaying detailed information about individual OIDs.
The OID registry helps in uniquely identifying various entities like vendors,
platforms, services, and applications within the Saturnin ecosystem.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from saturnin._scripts.completers import oid_completer
from saturnin.base import directory_scheme
from saturnin.lib.console import RICH_ERROR, RICH_OK, _h, console

from firebird.uuid import ROOT_SPEC, OIDNode, get_specifications, oid_registry, parse_specifications

#: Typer command group for OID management commands
app = typer.Typer(rich_markup_mode="rich", help="Saturnin OID management.")

@app.command()
def list_oids(
    with_name: Annotated[str, typer.Option(help="Filter: List only OIDs whose full name contains this string.")]='',
    *,
    show_oids: Annotated[bool, typer.Option('--show-oids',
                                            help="Display OIDs in dotted decimal notation instead of UUIDs.")]=False
    ) -> None:
    """Lists registered OIDs, optionally filtering by name.

    By default, OIDs are displayed as UUIDs. Use the `--show-oids` option
    to display them in their dotted decimal notation (e.g., 1.3.6.1.4.1.53446).
    """
    table = Table(title='Registered OIDs' if not with_name
                  else f"Registered OIDs with name containing '{with_name}'",
                  box=box.ROUNDED)
    table.add_column('OID Name', style='green')
    table.add_column('OID' if show_oids else 'UUID')
    if oid_registry:
        node: OIDNode
        # Sort for consistent output
        sorted_nodes = sorted(oid_registry.values(), key=lambda n: n.full_name)
        nodes_to_display = [node for node in sorted_nodes if with_name in node.full_name]

        if not nodes_to_display:
            console.print(f"No OIDs found with full name containing '{with_name}'.")
            return

        for node in nodes_to_display:
            identifier = Text(node.oid, style='number') if show_oids else Text(str(node.uid), style='uuid')
            table.add_row(node.full_name, identifier)
        console.print(table)
    else:
        console.print("No OIDs are registered.")

@app.command()
def update_oids(
    url: Annotated[str, typer.Argument(help="URL to the root OID node specification "
                                       "Defaults to the Firebird root specification.",
                                       metavar='URL')]=ROOT_SPEC
    ):
    """Updates the local OID registry by downloading and parsing specifications.

    This command fetches OID specifications starting from the given URL.
    The specifications can be linked, forming a tree of OID definitions.
    The local registry (stored in `oids.toml`) is then updated with the
    parsed information.
    """
    console.print(f"Downloading OID specifications starting from: [link={url}]{url}[/link] ... ", end='')
    specifications, errors = get_specifications(url)
    if errors:
        console.print(RICH_ERROR)
        console.print_error("Errors occurred during specification download:")
        for err_url, error in errors:
            console.print_error(f"  URL: [url]{err_url}[/url]")
            console.print_error(f"  Error: {error}")
        return
    console.print(RICH_OK)
    console.print("Parsing OID specifications ... ", end='')
    specifications, errors = parse_specifications(specifications)
    if errors:
        console.print(RICH_ERROR)
        console.print_error("Errors detected while parsing OID specifications:")
        for err_url, error in errors:
            console.print_error(f"  URL: [url]{err_url}[/url]")
            console.print_error(f"  Error: {error}")
        return
    console.print(RICH_OK)
    #
    console.print("Updating OID registry ... ", end='')
    try:
        oid_registry.update_from_specifications(specifications)
    except Exception as exc:
        console.print(RICH_ERROR)
        console.print_error(f"Failed to update registry from specifications:\n{exc}")
        return # Do not save if update itself failed
    console.print(RICH_OK)
    try:
        directory_scheme.site_oids_toml.write_text(oid_registry.as_toml())
        console.print(f"OID registry saved to: [path]{directory_scheme.site_oids_toml}[/path]")
    except Exception as exc:
        console.print_error(f"Failed to save OID registry to file: {exc}")

@app.command()
def show_oid(
    oid: Annotated[str, typer.Argument(help="The OID to display, specified by its full name or UUID.",
                                       autocompletion=oid_completer)]
    ) -> None:
    """Show information about OID.
    """
    uid: UUID = None
    name: str = None
    node: OIDNode = None
    try:
        uid = UUID(oid)
    except ValueError: # Not a valid UUID string
        name = oid
    except Exception: # Other potential errors during UUID conversion
        console.print_error(f"Invalid OID identifier format: [item]{oid}[/item]")
        return

    if uid is not None:
        node = oid_registry.get(uid)
    else:
        node = oid_registry.find(lambda x: x.full_name.startswith(name))
    if node is None:
        console.print_error(f"OID '[item]{oid}[/]' not found in the registry.")
        return

    table = Table.grid(padding=(0, 1))
    table.add_column(style='green', justify="right")
    table.add_column(overflow="fold")

    table.add_row('OID (Dotted Decimal):', Text(node.oid, style='number'))
    table.add_row('UUID:', _h(Text(str(node.uid))))
    table.add_row('Node Name:', Text(node.name))
    table.add_row('Full Name:', Text(node.full_name))
    table.add_row('Description:', Text(node.description or "[dim]Not provided[/dim]"))
    table.add_row('Contact:', Text(node.contact or "[dim]Not provided[/dim]"))
    table.add_row('E-mail:', _h(Text(node.email or "[dim]Not provided[/dim]")))
    table.add_row('Info Site URL:', _h(Text(node.site or "[dim]Not provided[/dim]")))
    table.add_row('Node Specification URL:', _h(Text(str(node.node_spec) or "[dim]Not provided[/dim]")))
    table.add_row('Node Type:', _h(Text(node.node_type.name)))
    table.add_row('Parent Specification URL:', _h(Text(str(node.parent_spec) or "[dim]Root node[/dim]")))

    console.print(Panel(table, title=f"[b]Details for OID: {node.full_name}[/b]",
                        border_style="dim", expand=False))


if directory_scheme.site_oids_toml.is_file():
    oid_registry.update_from_toml(directory_scheme.site_oids_toml.read_text())

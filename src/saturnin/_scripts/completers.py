# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: saturnin
#   FILE:           saturnin/_scripts/completers.py
#   DESCRIPTION:    CLI command completers
#   CREATED:        19.02.2023
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
# Initial code is based on https://github.com/click-contrib/click-repl
#
# Contributor(s): Pavel Císař (initial code)
#                 ______________________________________

"""CLI command completers.

These functions are designed for use with Typer/Click arguments and options
via the `autocompletion` parameter. They provide context-aware suggestions
to enhance the command-line user experience.
"""

from __future__ import annotations

from pathlib import Path

from saturnin.component.apps import application_registry
from saturnin.component.recipe import recipe_registry
from saturnin.component.registry import service_registry

from firebird.uuid import oid_registry


def get_first_line(text: str) -> str:
    """Returns the first non-empty line from the input string.
    """
    return text.strip().split('\n')[0]

def oid_completer(ctx, args, incomplete) -> list:
    """Click completer for OIDs.

    Provides completion suggestions based on registered OID UUIDs and their
    full names from the `.oid_registry`.

    Returns:
        A list of strings, where each string is either an OID's UUID
        or its full name.
    """
    result = [(str(oid.uid)) for oid in oid_registry.values()]
    result.extend(oid.full_name for oid in oid_registry.values())
    return result

def service_completer(ctx, args, incomplete) -> list:
    """Click completer for Saturnin services.

    Provides completion suggestions based on registered service UIDs and names
    from the `.service_registry`.

    Returns:
        A list of strings, where each string is either a service's UID
        or its name.
    """
    result = [(str(svc.uid)) for svc in service_registry.values()]
    result.extend(svc.name for svc in service_registry.values())
    return result

def application_completer(ctx, args, incomplete) -> list:
    """Click completer for Saturnin applications.

    Provides completion suggestions based on registered application UIDs and names
    from the `.application_registry`.

    Returns:
        A list of strings, where each string is either an application's UID
        or its name.
    """
    result = [(str(app.uid)) for app in application_registry.values()]
    result.extend(app.name for app in application_registry.values())
    return result

def recipe_completer(ctx, args, incomplete) -> list[tuple[str, str]]:
    """Click completer for Saturnin recipes.

    Provides completion suggestions based on installed recipe names from the
    `.recipe_registry`, along with their descriptions.

    Returns:
        A list of (value, help_text) tuples, where `value` is the recipe name
        and `help_text` is the first line of its description.
    """
    return [(recipe.name, get_first_line(recipe.description))
            for recipe in recipe_registry.values()]

def path_completer(ctx, args, incomplete) -> list:
    """Click completer for filesystem Path values.

    Provides completion suggestions by globbing for files and directories
    based on the `incomplete` path string. It navigates up to the nearest
    existing parent directory if the `incomplete` path itself doesn't exist.

    Returns:
        A list of strings, where each string is a potential path completion.
    """
    base_path = Path(incomplete)
    while not base_path.exists():
        base_path = base_path.parent
    return [str(path) for path in base_path.glob('*')]

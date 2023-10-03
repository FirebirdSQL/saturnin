# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/metadata.py
# DESCRIPTION:    Module for work with importlib metadata
# CREATED:        23.2.2023
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
# Copyright (c) 2023 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________
# pylint: disable=W0611

"""Module for work with importlib metadata


"""

from __future__ import annotations
from typing import Generator, Optional
from importlib.metadata import (entry_points, EntryPoint, Distribution, distributions,
                                distribution)

def iter_entry_points(group: str, name: str=None) -> Generator[EntryPoint, None, None]:
    """Replacement for pkg_resources.iter_entry_points.

    Arguments:
        group: Entrypoint group name
        name:  Etrypoint name.

    When `name` is specified, returns only EntryPoint with such name. When `name` is not
    specified, returns all entry points in group.
    """
    for item in entry_points().get(group, []):
        if name is None or item.name == name:
            yield item

def get_entry_point_distribution(entry_point: EntryPoint) -> Optional[Distribution]:
    """Returns distribution that registered specified entry point, or None if distribution
    is not found. This function searches through all distributions, not only those that
    registered Saturnin components.

    Arguments:
      entry_point: Entry point for which the distribution is to be found.
    """
    for dis in (d for d in distributions() if d.entry_points):
        for entry in dis.entry_points:
            if entry.name == entry_point.name:
                return dis
    return None

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

"""Utility functions for interacting with Python's importlib.metadata.

This module provides helper functions to simplify common tasks related to
discovering and inspecting package distributions and their registered entry points,
acting as a focused interface to `importlib.metadata` functionalities.
"""

from __future__ import annotations

from collections.abc import Generator
from importlib.metadata import Distribution, EntryPoint, distribution, distributions, entry_points  # noqa:F401


def iter_entry_points(group: str, name: str | None=None) -> Generator[EntryPoint, None, None]:
    """Provides an iterator for entry points, similar to `pkg_resources.iter_entry_points`.

    This function leverages `importlib.metadata.entry_points()` to find and
    yield `EntryPoint` objects.

    Arguments:
        group: The name of the entry point group to iterate over (e.g., 'console_scripts').
        name: Optional. The specific name of the entry point to retrieve.
              If `None`, all entry points within the specified group are yielded.

    Yields:
        EntryPoint: An `EntryPoint` object for each matching entry point found.
    """
    for item in entry_points().get(group, []):
        if name is None or item.name == name:
            yield item

def get_entry_point_distribution(entry_point: EntryPoint) -> Distribution | None:
    """Finds the distribution package that registered a given entry point.

    This function iterates through all available distributions to find the one
    containing the specified `entry_point`. It is not limited to distributions
    that might have registered specific Saturnin components but searches globally.

    Arguments:
        entry_point: The `EntryPoint` object for which the parent distribution
                     is to be located.

    Returns:
        Distribution | None: The `Distribution` object that registered the
                             `entry_point`, or `None` if no such distribution
                             can be found.
    """
    for dis in (d for d in distributions() if d.entry_points):
        for entry in dis.entry_points:
            if entry.name == entry_point.name:
                return dis
    return None

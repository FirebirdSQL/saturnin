#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/registry.py
# DESCRIPTION:    Component registration and discovery
# CREATED:        4.12.2020
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin component registration and discovery

Service registration
--------------------

Services are registered as entry points for their `ServiceDescriptor` - i.e. the instance
of `ServiceDescriptor` for installed service is returned by `EntryPoint.load()`.

The default group for service registration is `saturnin.service`, but it's possible to
install additional service discovery iterators.

Custom service iterator must be a generator that accepts optional `uid` in string format,
and yileds `EntryPoint` instances. If `uid` is specified, it must return only `EntryPoint`
only for service with given `uid`, otherwise it should return all services.

Note:

  Custom iterator can return objects that are not `EntryPoint` instances, but they MUST
  implement `load()` method that will return `ServiceDescriptor` instance.

Custom iterators must be registered as entry points in `saturnin.service.iterator` group.
"""

from __future__ import annotations
from typing import List, Generator
from functools import partial
from itertools import chain
from importlib.metadata import entry_points, EntryPoint
from saturnin.base import ServiceDescriptor, Error

def iter_entry_points(group: str, name: str=None) -> Generator[EntryPoint, None, None]:
    "Replacement for pkg_resources.iter_entry_points"
    for item in entry_points().get(group, []):
        if name is None or item.name == name:
            yield item

# Default service registration
_iterators = [partial(iter_entry_points, 'saturnin.service')]

# Load custom service iterators
for i in iter_entry_points('saturnin.service.iterator'):
    _iterators.append(i.load())

def get_service_desciptors(uid: str=None) -> List[ServiceDescriptor]:
    """Returns list of service descriptors for registered services.

    Arguments:
       uid: When specified, returns only descriptor for service with given `uid`.
    """
    result = []
    for entry in chain.from_iterable([i(uid) for i in _iterators]):
        try:
            result.append(entry.load())
        except Exception as exc:
            raise Error(f"Descriptor loading failed: {entry!s}") from exc
    return result

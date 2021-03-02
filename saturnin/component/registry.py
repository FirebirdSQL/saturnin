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


"""

from __future__ import annotations
from typing import List
from pkg_resources import iter_entry_points
from functools import partial
from itertools import chain
from saturnin.base import ServiceDescriptor, Error

_iterators = [partial(iter_entry_points, 'saturnin.service')]

for i in iter_entry_points('saturnin.service.iterator'):
    _iterators.append(i.load())

def get_service_desciptors(uid: str=None) -> List[ServiceDescriptor]:
    """Returns list of service descriptors for registered services.
    """
    result = []
    for e in chain.from_iterable([i(uid) for i in _iterators]):
        try:
            result.append(e.load())
        except Exception as exc:
            raise Error(f"Descriptor loading failed: {str(e)}") from exc
    return result

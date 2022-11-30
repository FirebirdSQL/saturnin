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
from typing import List, Generator, Set, Hashable, Optional
from functools import partial
from itertools import chain
from uuid import UUID
from importlib.metadata import entry_points, EntryPoint, Distribution, distributions
from toml import dumps, loads
from saturnin.base import ServiceDescriptor, Error
from firebird.base.types import Distinct
from firebird.base.collections import Registry

class ServiceInfo(Distinct):
    def __init__(self, *, uid: UUID, name: str, version: str, vendor: UUID,
                 classification: str, description: str, facilities: List[str],
                 api: List[UUID], factory: str, descriptor: str, distribution: str):
        #: Service UID
        self.uid: UUID = uid
        #: Service name
        self.name: str = name
        #: Service version
        self.version: str = version
        #: Service vendor UID
        self.vendor: UUID = vendor
        #: Service classification
        self.classification: str = classification
        #: Service description
        self.description: str = description
        #: List of service facilities
        self.facilities: List[str] = facilities
        #: List of interfaces provided by service
        self.api: List[UUID] = api
        #: Service factory specification (entry point)
        self.factory: str = factory
        #: Service descriptor specification (entry point)
        self.descriptor: str = descriptor
        #: Installed distribution package that contains this service
        self.distribution: str = distribution
    def get_key(self) -> Hashable:
        "Returns service UID"
        return self.uid
    def as_toml_dict(self) -> Dict:
        """Returns dictionary with instance data suitable for storage in TOML format
        (values that are not of basic type are converted to string).
        """
        return {'uid': str(self.uid),
                'name': self.name,
                'version': self.version,
                'vendor': str(self.vendor),
                'classification': self.classification,
                'description': self.description,
                'facilities': self.facilities,
                'api': [str(x) for x in self.api],
                'factory': self.factory,
                'descriptor': self.descriptor,
                'distribution': self.distribution,
                }

class ServiceRegistry(Registry):
    """Saturnin service registry.

    Holds `ServiceInfo` instances.
    """
    def load_from_installed(self, *, ignore_errors: bool=False) -> None:
        """Populate registry from descriptors of installed services.

        Arguments:
          ignore_errors: When True, errors are ignored, otherwise `.Error` is raised.
        """
        for entry in get_service_entry_points():
            args = {}
            d: Distribution = get_entry_point_distribution(entry)
            args['distribution'] = d if d is None else d.metadata['name']
            args['descriptor'] = entry.value
            try:
                desc: ServiceDescriptor = entry.load()
            except Exception as exc:
                if ignore_errors:
                    continue
                else:
                    raise Error(f"Failed to load service '{entry.name}' from '{args['distribution']}'") from exc
            args['uid'] = desc.agent.uid
            args['name'] = desc.agent.name
            args['version'] = desc.agent.version
            args['vendor'] = desc.agent.vendor_uid
            args['classification'] = desc.agent.classification
            args['description'] = desc.description
            args['facilities'] = desc.facilities
            args['api'] = [x.get_uid() for x in desc.api]
            args['factory'] = desc.factory
            try:
                svc_info = ServiceInfo(**args)
            except Exception as exc:
                if ignore_errors:
                    continue
                else:
                    raise Error(f"Malformed service descriptor for '{entry.name}' from '{args['distribution']}'") from exc
            self.store(svc_info)
    def load_from_toml(self, toml: str, *, ignore_errors: bool=False) -> None:
        """Populate registry from TOML document.

        Arguments:
          toml: TOML document (as created by `as_toml` method).
          ignore_errors: When True, errors are ignored, otherwise `.Error` is raised.
        """
        data = loads(toml)
        self.clear()
        for uid, kwargs in data.items():
            try:
                kwargs['uid'] = UUID(kwargs['uid'])
                kwargs['vendor'] = UUID(kwargs['vendor'])
                kwargs['api'] = [UUID(x) for x in kwargs['api']]
                svc_info = ServiceInfo(**kwargs)
            except Exception as exc:
                if ignore_errors:
                    continue
                else:
                    raise Error(f"Malformed service data for '{uid}' from '{kwargs['distribution']}'") from exc
            self.store(svc_info)
    def as_toml(self) -> str:
        """Returns registry content as TOML document.
        """
        nodes = {str(node.uid): node.as_toml_dict() for node in self._reg.values()}
        toml = dumps(nodes)
        return toml

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

def get_service_entry_points() -> List[EntryPoint]:
    """Returns list of entry points for registered services.
    """
    return [entry for entry in chain.from_iterable([i() for i in _iterators])]

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

def get_service_distributions() -> Set[Distribution]:
    """Returns list of distributions with Saturnin services.
    """
    result = set()
    entry_points = [e.name for e in chain.from_iterable([i() for i in _iterators])]
    for dis in (d for d in distributions() if d.entry_points):
        for entry in dis.entry_points:
            if entry.name in entry_points:
                result.add(dis)
    return result

def get_service_distribution_names() -> Set[str]:
    """Returns set with names of all distributions with Saturnin services.
    """
    return set(x.metadata['name'] for x in get_service_distributions())

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

service_registry: ServiceRegistry = ServiceRegistry()

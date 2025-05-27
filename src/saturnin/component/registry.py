# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

"""Saturnin component registration and discovery.

Services are registered as entry points where `EntryPoint.load()` is expected to return an
instance of .ServiceDescriptor.

The default group for service registration is `saturnin.service`, but it's possible to
install additional service discovery iterators.

Custom service iterator must be a generator that accepts optional `uid` in string format,
and yileds `importlib.metadata.EntryPoint` instances. If `uid` is specified, it must return
only `EntryPoint` only for service with given `uid`, otherwise it should return all services.

Note:

  Custom iterator can return objects that are not `~importlib.metadata.EntryPoint` instances,
  but they MUST implement `load()` method that will return `.ServiceDescriptor` instance.

Custom iterators must be registered as entry points in `saturnin.service.iterator` group.
"""

from __future__ import annotations

from collections.abc import Hashable
from contextlib import suppress
from functools import partial
from itertools import chain
from tomllib import loads
from typing import Any
from uuid import UUID

from saturnin.base import Error, ServiceDescriptor, directory_scheme
from saturnin.lib.metadata import get_entry_point_distribution, iter_entry_points
from tomli_w import dumps

from firebird.base.collections import Registry
from firebird.base.types import Distinct, load


class ServiceInfo(Distinct):
    """Information about service stored in  `.ServiceRegistry`.

    Arguments:
        uid: Service UID
        name: Service name
        version: Service version
        vendor: Service vendor UID
        classification: Service classification
        description: Service description
        facilities: List of service facilities
        api: List of interfaces provided by service
        factory: Service factory specification (entry point)
        descriptor: Service descriptor specification (entry point)
        distribution: Installed distribution package that contains this service
    """
    def __init__(self, *, uid: UUID, name: str, version: str, vendor: UUID,
                 classification: str, description: str, facilities: list[str],
                 api: list[UUID], factory: str, descriptor: str, distribution: str):
        self.__desc_obj: Any = None
        self.__fact_obj: Any = None
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
        self.facilities: list[str] = facilities
        #: List of interfaces provided by service
        self.api: list[UUID] = api
        #: Service factory specification (entry point)
        self.factory: str = factory
        #: Service descriptor specification (entry point)
        self.descriptor: str = descriptor
        #: Installed distribution package that contains this service
        self.distribution: str = distribution
    def get_key(self) -> Hashable:
        "Returns service UID"
        return self.uid
    def as_toml_dict(self) -> dict:
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
    def __get_descriptor_obj(self) -> ServiceDescriptor:
        """Service descriptor object. If it's not assigned directly, then it's loaded
        using `.descriptor` on first access.
        """
        if self.__desc_obj is None:
            self.__desc_obj = load(self.descriptor)
        return self.__desc_obj
    def __set_descriptor_obj(self, value: ServiceDescriptor | None) -> None:
        "Property setter"
        self.__desc_obj = value
    descriptor_obj = property(__get_descriptor_obj, __set_descriptor_obj, None,
                              __get_descriptor_obj.__doc__)
    def __get_factory_obj(self) -> Any:
        """Service factory object. If it's not assigned directly, then it's loaded
        using `.factory` on first access.
        """
        if self.__fact_obj is None:
            self.__fact_obj = load(self.factory)
        return self.__fact_obj
    def __set_factory_obj(self, value: Any | None) -> None:
        "Property setter"
        self.__fact_obj = value
    factory_obj = property(__get_factory_obj, __set_factory_obj, None, __get_factory_obj.__doc__)

class ServiceRegistry(Registry):
    """Saturnin service registry.

    Holds `.ServiceInfo` instances.

    It is used in two modes:

    1. In a full Saturnin deployment, information about services is loaded from a TOML file.
       Service descriptors and factories are then loaded on demand.
    2. In standalone service/bundle mode, service information, including service descriptors
       and factories, is stored directly by the executor script. This allows for scenarios
       where dynamic discovery is not used, and the application can be compiled (e.g., with Nuitka).
    """
    def add(self, descriptor: ServiceDescriptor, factory: Any, distribution: str) -> None:
        """Registers a service directly, typically used in environments that do not
        support or use dynamic entry point discovery (e.g., applications compiled with Nuitka).

        Arguments:
            descriptor: The `.ServiceDescriptor` instance for the service.
            factory: The factory object or callable for creating the service instance.
            distribution: The name of the distribution package that provides this service.
        """
        kwargs = {}
        kwargs['distribution'] = distribution
        kwargs['descriptor'] = ''
        kwargs['uid'] = descriptor.agent.uid
        kwargs['name'] = descriptor.agent.name
        kwargs['version'] = descriptor.agent.version
        kwargs['vendor'] = descriptor.agent.vendor_uid
        kwargs['classification'] = descriptor.agent.classification
        kwargs['description'] = descriptor.description
        kwargs['facilities'] = descriptor.facilities
        kwargs['api'] = [x.get_uid() for x in descriptor.api]
        kwargs['factory'] = descriptor.factory
        svc_info = ServiceInfo(**kwargs)
        svc_info.descriptor_obj = descriptor
        svc_info.factory_obj = factory
        self.store(svc_info)
    def load_from_installed(self, *, ignore_errors: bool=False) -> None:
        """Populate registry from descriptors of installed services.

        Arguments:
          ignore_errors: When True, errors are ignored, otherwise `.Error` is raised.
        """
        for entry in chain.from_iterable([i() for i in _iterators]):
            kwargs = {}
            dist = get_entry_point_distribution(entry)
            kwargs['distribution'] = dist if dist is None else dist.metadata['name']
            kwargs['descriptor'] = entry.value
            try:
                desc: ServiceDescriptor = entry.load()
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Failed to load service '{entry.name}' "
                            f"from '{kwargs['distribution']}'") from exc
            kwargs['uid'] = desc.agent.uid
            kwargs['name'] = desc.agent.name
            kwargs['version'] = desc.agent.version
            kwargs['vendor'] = desc.agent.vendor_uid
            kwargs['classification'] = desc.agent.classification
            kwargs['description'] = desc.description
            kwargs['facilities'] = desc.facilities
            kwargs['api'] = [x.get_uid() for x in desc.api]
            kwargs['factory'] = desc.factory
            try:
                svc_info = ServiceInfo(**kwargs)
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Malformed service descriptor for '{entry.name}' "
                            f"from '{kwargs['distribution']}'") from exc
            with suppress(ValueError):
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
                raise Error(f"Malformed service data for '{uid}' "
                            f"from '{kwargs['distribution']}'") from exc
            self.store(svc_info)
    def as_toml(self) -> str:
        """Returns registry content as TOML document.
        """
        nodes = {str(node.uid): node.as_toml_dict() for node in self._reg.values()}
        return dumps(nodes)
    def load(self) -> None:
        """Reads information about installed services from a previously saved TOML file,
        located at `.directory_scheme.site_services_toml`, if it exists.
        """
        if directory_scheme.site_services_toml.is_file():
            service_registry.load_from_toml(directory_scheme.site_services_toml.read_text())
    def save(self) -> None:
        """Saves the current information about installed services to a TOML file located
        at `.directory_scheme.site_services_toml`.
        """
        directory_scheme.site_services_toml.write_text(service_registry.as_toml())
    def get_by_name(self, name: str, default: Any=None) -> Distinct:
        """Get service by its name.

        Arguments:
            name: Service name.
            default: Default value returned when service is not found.
        """
        return self.find(lambda x: x.name == name, default=default)

# Default service registration
_iterators = [partial(iter_entry_points, 'saturnin.service')]

# Load custom service iterators
for i in iter_entry_points('saturnin.service.iterator'):
    _iterators.append(i.load())

#: Global `ServiceRegistry` instance, automatically populated by load() upon module import.
service_registry: ServiceRegistry = ServiceRegistry()
service_registry.load()

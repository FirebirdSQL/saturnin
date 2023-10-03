# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/apps.py
# DESCRIPTION:    Application registration and discovery
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

"""Saturnin application registration and discovery.

Applications are registered as entry points for their `.ApplicationDescriptor` - i.e.
the instance of `.ApplicationDescriptor` for installed service is returned by `.EntryPoint.load()`.

The entry point group for service registration is `saturnin.application`.
"""

from __future__ import annotations
from typing import Dict, Hashable, Optional, Any
from uuid import UUID
from contextlib import suppress
from toml import dumps, loads
from firebird.base.types import Distinct, load
from firebird.base.collections import Registry
from saturnin.base import directory_scheme, ApplicationDescriptor, Error
from saturnin.lib.metadata import get_entry_point_distribution, iter_entry_points

class ApplicationInfo(Distinct): # pylint: disable=R0902
    """Information about application stored in  `.ApplicationRegistry`.

    Arguments:
        uid: Application UID
        name: Application name
        version: Application version
        vendor: Application vendor UID
        classification: Application classification
        description: Application description
        factory: Application factory specification (entry point)
        config: Application configuration factory (entry point)
        descriptor: Application descriptor specification (entry point)
        distribution: Installed distribution package that contains this application
    """
    def __init__(self, *, uid: UUID, name: str, version: str, vendor: UUID,
                 classification: str, description: str, factory: str, config: str,
                 descriptor: str, distribution: str):
        self.__desc_obj: Any = None
        self.__fact_obj: Any = None
        self.__conf_obj: Any = None
        #: Application UID
        self.uid: UUID = uid
        #: Application name
        self.name: str = name
        #: Application version
        self.version: str = version
        #: Application vendor UID
        self.vendor: UUID = vendor
        #: Application classification
        self.classification: str = classification
        #: Application description
        self.description: str = description
        #: Application command factory specification (entry point)
        self.factory: str = factory
        #: Application configuration factory (entry point)
        self.config: str = config
        #: Application descriptor specification (entry point)
        self.descriptor: str = descriptor
        #: Installed distribution package that contains this application
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
                'factory': self.factory,
                'config': self.config,
                'descriptor': self.descriptor,
                'distribution': self.distribution,
                }
    def get_recipe_name(self) -> str:
        """Returns default recipe name for this application. If application name contains
        dots, only part after last dot is returned. Otherwise it returns the application name.
        """
        return self.name.split('.')[-1]
    @property
    def descriptor_obj(self) -> ApplicationDescriptor:
        """Application descriptor object. If it's not assigned directly, then it's loaded
        using `.descriptor` on first access.
        """
        if self.__desc_obj is None:
            self.__desc_obj = load(self.descriptor)
        return self.__desc_obj
    @descriptor_obj.setter
    def set_descriptor_obj(self, value: Optional[ApplicationDescriptor]) -> None:
        "Property setter"
        self.__desc_obj = value
    @property
    def factory_obj(self) -> Any:
        """Application command factory object. If it's not assigned directly, then it's loaded
        using `.factory` on first access.
        """
        if self.__fact_obj is None:
            self.__fact_obj = load(self.factory)
        return self.__fact_obj
    @factory_obj.setter
    def set_factory_obj(self, value: Optional[Any]) -> None:
        "Property setter"
        self.__fact_obj = value
    @property
    def config_obj(self) -> Any:
        """Application configuration factory object. If it's not assigned directly, then it's loaded
        using `.config` on first access.
        """
        if self.__conf_obj is None:
            self.__conf_obj = load(self.config)
        return self.__conf_obj
    @factory_obj.setter
    def set_config_obj(self, value: Optional[Any]) -> None:
        "Property setter"
        self.__conf_obj = value

class ApplicationRegistry(Registry):
    """Saturnin application registry.

    Holds `.ApplicationInfo` instances.

    It is used in two modes:

    1. In full saturnin deployment, the information about applications is loaded from TOML file.
       Application descriptors and factories are loaded on demand.
    2. In standalone service/bundle mode, application information including app. desciptors
       and factories is stored directly by executor script, so there is no dynamic discovery
       and the whole could be compiled with Nutika.
    """
    def add(self, descriptor: ApplicationDescriptor, factory: Any, distribution: str) -> None:
        """Direct application registration. Used by systems that does not allow dynamic discovery,
        for example programs compiled by Nuitka.

        Arguments:
            descriptor: Application descriptor
            factory: Application factory
            distribution: Distribution package name with application
        """
        kwargs = {}
        kwargs['distribution'] = distribution
        kwargs['descriptor'] = ''
        kwargs['uid'] = descriptor.uid
        kwargs['name'] = descriptor.name
        kwargs['version'] = descriptor.version
        kwargs['vendor'] = descriptor.vendor_uid
        kwargs['classification'] = descriptor.classification
        kwargs['description'] = descriptor.description
        kwargs['factory'] = descriptor.factory
        kwargs['config'] = descriptor.config
        app_info = ApplicationInfo(**kwargs) # pylint: disable=E1125
        app_info.descriptor_obj = descriptor
        app_info.factory_obj = factory
        self.store(app_info)
    def load_from_installed(self, *, ignore_errors: bool=False) -> None:
        """Populate registry from descriptors of installed applications.

        Arguments:
          ignore_errors: When True, errors are ignored, otherwise `.Error` is raised.
        """
        for entry in iter_entry_points('saturnin.application'):
            kwargs = {}
            dist = get_entry_point_distribution(entry)
            kwargs['distribution'] = dist if dist is None else dist.metadata['name']
            kwargs['descriptor'] = entry.value
            try:
                desc: ApplicationDescriptor = entry.load()
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Failed to load application '{entry.name}' "
                            f"from '{kwargs['distribution']}'") from exc
            kwargs['uid'] = desc.uid
            kwargs['name'] = desc.name
            kwargs['version'] = desc.version
            kwargs['vendor'] = desc.vendor_uid
            kwargs['classification'] = desc.classification
            kwargs['description'] = desc.description
            kwargs['factory'] = desc.factory
            kwargs['config'] = desc.config
            try:
                app_info = ApplicationInfo(**kwargs) # pylint: disable=E1125
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Malformed application descriptor for '{entry.name}' "
                            f"from '{kwargs['distribution']}'") from exc
            with suppress(ValueError):
                self.store(app_info)
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
                app_info = ApplicationInfo(**kwargs)
            except Exception as exc:
                if ignore_errors:
                    continue
                raise Error(f"Malformed application data for '{uid}' "
                            f"from '{kwargs['distribution']}'") from exc
            self.store(app_info)
    def as_toml(self) -> str:
        """Returns registry content as TOML document.
        """
        nodes = {str(node.uid): node.as_toml_dict() for node in self._reg.values()}
        return dumps(nodes)
    def load(self) -> None:
        "Read information about installed applications from previously saved TOML file."
        if directory_scheme.site_apps_toml.is_file():
            application_registry.load_from_toml(directory_scheme.site_apps_toml.read_text())
    def save(self) -> None:
        "Save information about installed applications to TOML file."
        directory_scheme.site_apps_toml.write_text(application_registry.as_toml())
    def get_by_name(self, name: str, default: Any=None) -> Distinct:
        """Get application by its name.

        Arguments:
            name: Application name.
            default: Default value returned when application is not found.
        """
        return self.find(lambda x: x.name == name, default=default)

#: Saturnin application registry
application_registry: ApplicationRegistry = ApplicationRegistry()
application_registry.load()

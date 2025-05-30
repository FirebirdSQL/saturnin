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

This module handles the registration and discovery of Saturnin applications.
Applications are registered as entry points where `.EntryPoint.load()` is
expected to return an instance of `.ApplicationDescriptor`. The default
entry point group for application registration is `saturnin.application`.

It provides `.ApplicationInfo` to represent application metadata and
`.ApplicationRegistry` to manage these applications.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from contextlib import suppress
from tomllib import loads
from typing import Any, TypeAlias
from uuid import UUID

from saturnin.base import ApplicationDescriptor, Error, directory_scheme
from saturnin.base.types import GenericCallable
from saturnin.lib.metadata import get_entry_point_distribution, iter_entry_points
from tomli_w import dumps

from firebird.base.collections import Registry
from firebird.base.types import Distinct, load

TAppRecipeFactory: TypeAlias = Callable[[], str]

class ApplicationInfo(Distinct):
    """Information about application stored in  `.ApplicationRegistry`.

    Arguments:
        uid: Application UID
        name: Application name
        version: Application version
        vendor: Application vendor UID
        classification: Application classification
        description: Application description
        cli_command: Application factory specification (entry point)
        recipe_factory: Application configuration factory (entry point)
        descriptor: Application descriptor specification (entry point)
        distribution: Installed distribution package that contains this application
    """
    def __init__(self, *, uid: UUID, name: str, version: str, vendor: UUID,
                 classification: str, description: str, descriptor: str, distribution: str,
                 cli_command: str | None = None, recipe_factory: str | None = None):
        self.__descriptor: Any = None
        self.__cli_command: Any = None
        self.__recipe_factory: Any = None
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
        #: Application command specification (entry point)
        self.cli_command: str | None = cli_command
        #: Application recipe factory (entry point)
        self.recipe_factory: str | None = recipe_factory
        #: Application descriptor specification (entry point)
        self.descriptor: str = descriptor
        #: Installed distribution package that contains this application
        self.distribution: str = distribution
    def get_key(self) -> Hashable:
        "Returns the application UID, which serves as its unique key."
        return self.uid
    def as_toml_dict(self) -> dict:
        """Returns dictionary with instance data suitable for storage in TOML format
        (values that are not of basic type are converted to string).
        """
        return {k: v for k, v in {'uid': str(self.uid),
                'name': self.name,
                'version': self.version,
                'vendor': str(self.vendor),
                'classification': self.classification,
                'description': self.description,
                'cli_command': self.cli_command,
                'recipe_factory': self.recipe_factory,
                'descriptor': self.descriptor,
                'distribution': self.distribution,
                }.items() if v is not None}
    def get_recipe_name(self) -> str:
        """Returns default recipe name for this application. If application name contains
        dots, only part after last dot is returned. Otherwise it returns the application name.
        """
        return self.name.split('.')[-1]
    def is_command(self) -> bool:
        """Returns tru if application is console command.

        Such applications are not installed via recipe, but directly into console.
        """
        return self.recipe_factory is None
    @property
    def descriptor_obj(self) -> ApplicationDescriptor:
        """Application descriptor object. If it's not assigned directly, then it's loaded
        using `.descriptor` on first access.
        """
        if self.__descriptor is None:
            self.__descriptor = load(self.descriptor)
        return self.__descriptor
    @descriptor_obj.setter
    def set_descriptor_obj(self, value: ApplicationDescriptor | None) -> None:
        """Sets the application descriptor object directly, bypassing lazy loading for
        subsequent accesses of descriptor_obj."""
        self.__descriptor = value
    @property
    def cli_command_obj(self) -> GenericCallable:
        """Application command factory object. If it's not assigned directly, then it's loaded
        using `.factory` on first access.
        """
        if self.__cli_command is None:
            self.__cli_command = load(self.cli_command)
        return self.__cli_command
    @cli_command_obj.setter
    def set_cli_command_obj(self, value: GenericCallable | None) -> None:
        """Sets the application factory object directly, bypassing lazy loading for
        subsequent accesses of factory_obj."""
        self.__cli_command = value
    @property
    def recipe_factory_obj(self) -> TAppRecipeFactory:
        """Application configuration factory object. If it's not assigned directly, then it's loaded
        using `.config` on first access.
        """
        if self.__recipe_factory is None:
            self.__recipe_factory = load(self.recipe_factory)
        return self.__recipe_factory
    @recipe_factory_obj.setter
    def set_recipe_factory_obj(self, value: TAppRecipeFactory) -> None:
        """Sets the application config object directly, bypassing lazy loading for
        subsequent accesses of config_obj."""
        self.__recipe_factory = value

class ApplicationRegistry(Registry):
    """Saturnin application registry.

    Holds `.ApplicationInfo` instances.

    It is used in two modes:

    1. In a full Saturnin deployment, information about applications is loaded from a TOML file.
       Application descriptors and factories are then loaded on demand.
    2. In standalone service/bundle mode, application information, including application descriptors
       and factories, is stored directly by the executor script. This allows for scenarios
       where dynamic discovery is not used, and the application can be compiled (e.g., with Nuitka).
    """
    def add(self, descriptor: ApplicationDescriptor, factory: Any, distribution: str) -> None:
        """Direct application registration. Used by systems that do not allow dynamic discovery,
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
        kwargs['factory'] = descriptor.cli_command
        kwargs['config'] = descriptor.recipe_factory
        app_info = ApplicationInfo(**kwargs)
        app_info.descriptor_obj = descriptor
        app_info.cli_command_obj = factory
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
            kwargs['cli_command'] = desc.cli_command
            kwargs['recipe_factory'] = desc.recipe_factory
            try:
                app_info = ApplicationInfo(**kwargs)
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
        """Reads information about installed applications from a previously saved TOML file,
        located at `.directory_scheme.site_apps_toml`, if it exists.
        """
        if directory_scheme.site_apps_toml.is_file():
            application_registry.load_from_toml(directory_scheme.site_apps_toml.read_text())
    def save(self) -> None:
        """Saves the current information about installed applications to a TOML file located
        at `.directory_scheme.site_apps_toml`.
        """
        directory_scheme.site_apps_toml.write_text(application_registry.as_toml())
    def get_by_name(self, name: str, default: Any=None) -> Distinct:
        """Get application by its name.

        Arguments:
            name: Application name.
            default: Default value returned when application is not found.
        """
        return self.find(lambda x: x.name == name, default=default)

#: Global `ApplicationRegistry` instance, automatically populated by load() upon module import.
application_registry: ApplicationRegistry = ApplicationRegistry()
application_registry.load()

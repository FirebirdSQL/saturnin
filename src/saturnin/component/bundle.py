# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/bundle.py
# DESCRIPTION:    Service budle controller and executor
# CREATED:        5.12.2020
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

"""Saturnin service bundle controller and executor.

This module provides `.BundleThreadController` and `.BundleExecutor` classes
to streamline the process of configuring, starting, and managing a collection
of Saturnin services as a single unit (a "bundle"). It acts as a
higher-level abstraction, coordinating multiple internal `.ThreadController`
instances, one for each service in the bundle.
"""

from __future__ import annotations

import uuid
import warnings
from configparser import DEFAULTSECT, ConfigParser
from pathlib import Path
from typing import Self

import zmq
from saturnin.base import (
    SECTION_BUNDLE,
    SECTION_LOCAL_ADDRESS,
    SECTION_NET_ADDRESS,
    SECTION_NODE_ADDRESS,
    SECTION_PEER_UID,
    SECTION_SERVICE_UID,
    ChannelManager,
    Config,
    Error,
)

from firebird.base.config import ConfigListOption, EnvExtendedInterpolation
from firebird.base.logging import FStrMessage as _m
from firebird.base.logging import get_logger
from firebird.base.trace import TracedMixin
from firebird.base.types import ZMQDomain

from .controller import Outcome, ServiceExecConfig, ThreadController
from .registry import service_registry


class ServiceBundleConfig(Config):
    """Service bundle configuration.

    Arguments:
        name: Conf. section name
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Agents (services) in bundle
        self.agents: ConfigListOption = ConfigListOption('agents', ServiceExecConfig,
           "A list of service configurations (ServiceExecConfig instances or their section names)\ndefining the services included in this bundle.",
           required=True)

class BundleThreadController(TracedMixin):
    """Service controller that manages collection of services executed in separate threads.

    Arguments:
        parser: ConfigParser instance to be used for bundle configuration.
        manager: ChannelManager to be used. If None, a new one is created.
    """
    def __init__(self, *, parser: ConfigParser | None=None, manager: ChannelManager | None=None):
        #: Channel manager
        self.mngr: ChannelManager = manager
        self._ext_mngr: bool = manager is not None
        if manager is None:
            self.mngr = ChannelManager(zmq.Context.instance())
        #: ConfigParser with service bundle configuration
        self.config: ConfigParser = \
            ConfigParser(interpolation=EnvExtendedInterpolation()) if parser is None else parser
        #: List with ThreadControllers for all service instances in bundle
        self.services: list[ThreadController] = []
        #: Registry with ServiceDescriptors for services that could be run
        #
        self.config[SECTION_LOCAL_ADDRESS] = {}
        self.config[SECTION_NODE_ADDRESS] = {}
        self.config[SECTION_NET_ADDRESS] = {}
        self.config[SECTION_SERVICE_UID] = {}
        self.config[SECTION_PEER_UID] = {}
        # Defaults
        self.config[DEFAULTSECT]['here'] = str(Path.cwd())
        # Assign Agent IDs for available services
        self.config[SECTION_SERVICE_UID].update((sd.name, sd.uid.hex) for sd
                                                in service_registry)
    def configure(self, *, section: str=SECTION_BUNDLE) -> None:
        """Configures the service bundle and all its constituent services.

        This method loads the main bundle configuration to identify the services
        it contains. Then, for each service in the bundle, it instantiates
        and configures an internal `.ThreadController`.

        Arguments:
            section: The name of the configuration section that defines the
                     service bundle (listing its member services). Defaults
                     to `SECTION_BUNDLE`.
        """
        svc_cfg: ServiceExecConfig = ServiceExecConfig(section)
        bundle_cfg: ServiceBundleConfig = ServiceBundleConfig(section)
        bundle_cfg.load_config(self.config)
        bundle_cfg.validate()
        # Assign Peer IDs to service sections (instances)
        peer_uids = {a_section.name: uuid.uuid1() for a_section in bundle_cfg.agents.value}
        self.config[SECTION_PEER_UID].update((k, v.hex) for k, v in peer_uids.items())
        #
        #
        for svc_cfg in bundle_cfg.agents.value:
            svc_cfg.validate()
            if svc_cfg.agent.value in service_registry:
                controller = ThreadController(service_registry[svc_cfg.agent.value],
                                              name=svc_cfg.name, peer_uid=peer_uids[svc_cfg.name],
                                              manager=self.mngr)
                self.services.append(controller)
            else:
                self.services.clear()
                raise Error(f"Unknonw agent in section '{svc_cfg.name}'")
    def start(self, *, timeout: int=10000) -> None:
        """Start all services in bundle.

        Arguments:
            timeout: Timeout for starting each service. None (infinity), or a floating
                     point number specifying a timeout for the operation in seconds (or
                     fractions thereof) [Default: 10s].

        Important:
            Services are started in order they are listed in bundle configuration.
            If any service fails to start, all previously started services are stopped.

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When service does not start in time.
        """
        for controller in self.services:
            try:
                controller.configure(self.config, controller.name)
                controller.start(timeout=timeout)
                if controller.endpoints:
                    # Update addresses for binded endpoints
                    for name, addresses in controller.endpoints.items():
                        opt_name = f'{controller.name}.{name}'
                        for address in addresses:
                            if address.domain == ZMQDomain.LOCAL:
                                self.config[SECTION_LOCAL_ADDRESS][opt_name] = address
                            elif address.domain == ZMQDomain.NODE:
                                self.config[SECTION_NODE_ADDRESS][opt_name] = address
                            else:
                                self.config[SECTION_NET_ADDRESS][opt_name] = address
            except:
                self.stop()
                raise
    def stop(self, *, timeout: int=10000) -> None:
        """Stop all runing services in bundle. The services are stopped in the reverse
        order in which they were started.

        Arguments:
            timeout: Timeout for stopping each service. None (infinity), or a floating
                     point number specifying a timeout for the operation in seconds (or
                     fractions thereof) [Default: 10s].

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When service does not stop in time.
        """
        for controller in reversed(self.services):
            try:
                controller.stop(timeout=timeout)
            except Exception as exc:
                get_logger(self).error(_m("Error while stopping the service: {args[0]}", args=exc.args))
                if controller.is_running():
                    warnings.warn(f"Stopping service {controller.name} failed, "
                                  f"service thread terminated", RuntimeWarning)
                    controller.terminate()
    def join(self, timeout=None) -> None:
        """Wait until all services stop.

        Arguments:
            timeout: Floating point number specifying a timeout for the operation in
                     seconds (or fractions thereof).
        """
        for svc in self.services:
            svc.join(timeout)

class BundleExecutor:
    """A context manager for executing a bundle of Saturnin services.

    This class simplifies the lifecycle management of a `.BundleThreadController`,
    ensuring proper initialization and cleanup (like ZMQ context termination)
    when used in a `with` statement.
    """
    def __init__(self):
        #: Channel manager
        self.mngr: ChannelManager = None
        #: Controller
        self.controller: BundleThreadController = None
    def __enter__(self) -> Self:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.mngr is not None:
            self.mngr.shutdown(forced=True)
        zmq.Context.instance().term()
    def configure(self, cfg_files: list[str], *, section: str=SECTION_BUNDLE) -> None:
        """Initializes and configures the internal `BundleThreadController`.

        This involves creating a `.ChannelManager`, instantiating a
        `.BundleThreadController`, reading configuration files into the
        controller's `.ConfigParser`, and then calling the controller's
        `configure` method to set up all services in the bundle.

        Arguments:
          cfg_files: A list of paths to configuration files to be read.
          section:   The name of the configuration section that defines the
                     service bundle. Defaults to `SECTION_BUNDLE`.
        """
        self.mngr = ChannelManager(zmq.Context.instance())
        self.controller: BundleThreadController = BundleThreadController(manager=self.mngr)
        self.controller.config.read(cfg_files)
        self.controller.configure(section=section)
    def run(self) -> list[tuple[str, Outcome, list[str]]]:
        """Runs services in bundle.

        Returns:
          List with (service_name, outcome, details) tuples.

        Tuple items:

        - service_name: Name used for service in bundle configuration.
        - outcome: `.Outcome` of service execution.
        - details: List of strings with additional outcome information (typically error text)
        """
        self.controller.start()
        try:
            self.controller.join()
            raise KeyboardInterrupt() # This, or direct call to executor.stop()
        except KeyboardInterrupt: # SIGINT
            self.controller.stop()
        finally:
            result = []
            for svc in self.controller.services:
                result.append((svc.name, svc.outcome, svc.details))
        return result

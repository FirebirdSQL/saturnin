# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/service.py
# DESCRIPTION:    Base module for implementation of Firebird Butler Services
# CREATED:        22.4.2019
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
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Saturnin base module for implementation of Firebird Butler Services

It extends `MicroService` to provide a foundation for components that listen for and process
client requests using the Firebird Butler Service Protocol (FBSP).
"""

from __future__ import annotations

import uuid
from abc import abstractmethod
from typing import Final, cast

import zmq
from saturnin.base import ComponentConfig, RouterChannel, ServiceDescriptor, ZMQAddress
from saturnin.component.micro import MicroService
from saturnin.protocol.fbsp import FBSPService

from firebird.base.config import ListOption

#: Channel name
SVC_CHN: Final[str] = 'service'

class ServiceConfig(ComponentConfig):
    """Configuration for Firebird Butler Services.

    This class defines settings specific to `Service` components, primarily
    the network endpoints on which the service will listen for client connections.

    Arguments:
        name: Default configuration section name, typically the service name.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Service endpoint addresses
        self.endpoints: ListOption = \
            ListOption('endpoints', ZMQAddress, "List of service endpoints", required=True)

class Service(MicroService):
    """Base class for Firebird Butler Services.

    This class extends `MicroService` to implement a server component that communicates
    with clients using the Firebird Butler Service Protocol (FBSP) over a ZMQ `ROUTER`
    socket. It handles the setup of the FBSP service protocol and expects subclasses to
    register specific API handlers.

    Arguments:
        zmq_context: ZeroMQ Context.
        descriptor: Service descriptor.
        peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID | None=None):
        super().__init__(zmq_context, descriptor, peer_uid=peer_uid)
        #: Channel for communication with service clients.
        self.svc_channel: RouterChannel = None
    def initialize(self, config: ServiceConfig) -> None:
        """Verify configuration and assemble service structural parts.

        Arguments:
            config: Service configuration.
        """
        super().initialize(config)
        # Set endpoints this service binds
        self.endpoints[SVC_CHN] = config.endpoints.value.copy()
        #: Service protocol
        service = FBSPService(service=self.descriptor, peer=self.peer)
        self.svc_channel = self.mngr.create_channel(RouterChannel, SVC_CHN, service,
                                                    routing_id=self.peer.uid.hex.encode('ascii'),
                                                    sock_opts={'maxmsgsize': 52428800,
                                                               'rcvhwm': 500,
                                                               'sndhwm': 500,})
        self.register_api_handlers(service)
    @abstractmethod
    def register_api_handlers(self, service: FBSPService) -> None:
        """Called by `.initialize()` to allow subclasses to register their specific API
        handlers and FBSP service event handlers.

        Implementations of this method should use the provided `service` protocol instance
        to register handlers for various FBSP message types and API calls defined by the service.

        Arguments:
            service: The `FBSPService` protocol instance associated with this service's
                     main communication channel.
        """
    def start_activities(self) -> None:
        """Starts normal service activities.

        This typically involves enabling the service to accept incoming client
        requests on its main channel. Must raise an exception if starting
        activities fails.
        """
        super().start_activities()
        self.svc_channel.set_wait_in(True)
    def stop_activities(self) -> None:
        """Stop service activities.

        Calls `.FBSPService.close` and disables receiving incoming messages on the channel.
        """
        super().stop_activities()
        cast(FBSPService, self.svc_channel.protocol).close(self.svc_channel)
        self.svc_channel.set_wait_in(False)

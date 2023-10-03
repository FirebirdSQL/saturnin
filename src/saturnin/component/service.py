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
# pylint: disable=R0903

"""Saturnin base module for implementation of Firebird Butler Services
"""

from __future__ import annotations
from typing import cast, Final
from abc import abstractmethod
import uuid
import zmq
from firebird.base.config import ListOption
from saturnin.base import ZMQAddress, RouterChannel, ComponentConfig, ServiceDescriptor
from saturnin.component.micro import MicroService
from saturnin.protocol.fbsp import FBSPService

#: Channel name
SVC_CHN: Final[str] = 'service'

class ServiceConfig(ComponentConfig):
    """Base data provider/consumer microservice configuration.

    Arguments:
        name: Default configuration section name (service name)
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Service endpoint addresses
        self.endpoints: ListOption = \
            ListOption('endpoints', ZMQAddress, "List of service endpoints", required=True)

class Service(MicroService):
    """Base Firebird Butler Service.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID=None):
        """
        Arguments:
            zmq_context: ZeroMQ Context.
            descriptor: Service descriptor.
            peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
        """
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
        service.log_context = self.logging_id
        self.svc_channel = self.mngr.create_channel(RouterChannel, SVC_CHN, service,
                                                    routing_id=self.peer.uid.hex.encode('ascii'),
                                                    sock_opts={'maxmsgsize': 52428800,
                                                               'rcvhwm': 500,
                                                               'sndhwm': 500,})
        self.register_api_handlers(service)
    @abstractmethod
    def register_api_handlers(self, service: FBSPService) -> None:
        """Called by `.initialize()` for registration of service API handlers and FBSP
        service event handlers.

        Arguments:
            service: Service instance
        """
    def start_activities(self) -> None:
        """Start normal service activities.

        Must raise an exception when start fails.
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

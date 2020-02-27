#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service
# FILE:           saturnin/service/node/api.py
# DESCRIPTION:    API for Saturnin runtime node service
# CREATED:        12.5.2019
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

"""Saturnin - Runtime node service API

NODE Service manages Saturnin runtime node. It provides environment for execution and
management of other Saturnin services.

Supported requests:

    :INSTALLED_SERVICES:  REPLY with list of installed services available for execution on the node.
    :RUNNING_SERVICES:    REPLY with list of services actually running on the node.
    :INTERFACE_PROVIDERS: REPLY with list of installed services that provide specified interface.
    :START_SERVICE:       Start service on node.
    :STOP_SERVICE:        Stop service running on node.
    :SHUTDOWN:            Shuts down the NODE service.
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import Enum, ExecutionMode, ServiceType, ServiceFacilities, \
     AgentDescriptor, InterfaceDescriptor, ServiceDescriptor
from saturnin.core.config import ServiceConfig, create_config


# OID: iso.org.dod.internet.private.enterprise.firebird.butler.service.node
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.1.1'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1'

# firebird.butler.service.node.interface
NODE_INTERFACE_OID: str = '1.3.6.1.4.1.53446.1.1.1.0'
NODE_INTERFACE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, NODE_INTERFACE_OID)

# Enums (Request and Error Codes)

class NodeRequest(Enum):
    "Saturnin Node Service Request Code"
    INSTALLED_SERVICES = 1
    RUNNING_SERVICES = 2
    INTERFACE_PROVIDERS = 3
    START_SERVICE = 4
    STOP_SERVICE = 5
    SHUTDOWN = 6

class NodeError(Enum):
    "Saturnin Node Service Error Code"
    ALREADY_RUNNING = 1
    START_FAILED = 2
    TERMINATION_FAILED = 3

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="saturnin-node",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="system/runtime")

SERVICE_INTERFACE: InterfaceDescriptor = \
    InterfaceDescriptor(uid=NODE_INTERFACE_UID,
                        name="Saturnin Node service API",
                        revision=1, number=1,
                        requests=NodeRequest)

SERVICE_API = [SERVICE_INTERFACE]

SERVICE_DESCRIPTOR: ServiceDescriptor = \
    ServiceDescriptor(agent=SERVICE_AGENT,
                      api=SERVICE_API,
                      dependencies=[],
                      execution_mode=ExecutionMode.ANY,
                      service_type=ServiceType.CONTROL,
                      facilities=ServiceFacilities.FBSP_SOCKET,
                      description="Saturnin runtime node service",
                      implementation='saturnin.service.node.service:SaturninNodeServiceImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, ServiceConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "NODE service."),
                      client='saturnin.service.node.client:SaturninNodeClient',
                      tests='saturnin.service.node.test:TestRunner')

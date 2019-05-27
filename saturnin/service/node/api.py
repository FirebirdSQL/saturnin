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
    :INTERFACE_PROVIDERS: REPLY with list of services that provide specified interface.
    :START_SERVICE:       Start service on node.
    :STOP_SERVICE:        Stop service running on node.
    :REQUEST_PROVIDER:    REPLY with address for most efficient connection to the servie
                          that provides specified interface. Starts the service if necessary.
    :SHUTDOWN:            Shuts down the NODE service.
"""

from enum import IntEnum
from uuid import UUID, NAMESPACE_OID, uuid5
from saturnin.sdk import VENDOR_UID
from saturnin.sdk.types import AgentDescriptor, InterfaceDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType

SERVICE_OID: str = '1.3.6.1.4.1.53446.1.1.1' # firebird.butler.service.node
SERVICE_UID: UUID = uuid5(NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1'

NODE_INTERFACE_OID: str = '1.3.6.1.4.1.53446.1.1.1.0' # firebird.butler.service.node.interface
NODE_INTERFACE_UID: UUID = uuid5(NAMESPACE_OID, NODE_INTERFACE_OID)

#  Request Codes

class SaturninNodeRequest(IntEnum):
    "Saturnin Node Service Request Code"
    INSTALLED_SERVICES = 1
    RUNNING_SERVICES = 2
    INTERFACE_PROVIDERS = 3
    START_SERVICE = 4
    STOP_SERVICE = 5
    REQUEST_PROVIDER = 6
    SHUTDOWN = 7

#  Service description

SERVICE_AGENT = AgentDescriptor(SERVICE_UID,
                                "saturnin-node",
                                SERVICE_VERSION,
                                VENDOR_UID,
                                "saturnin/runtime",
                               )
SERVICE_INTERFACE = InterfaceDescriptor(NODE_INTERFACE_UID, "Saturnin Node service API", 1,
                                        SaturninNodeRequest)
SERVICE_API = [SERVICE_INTERFACE]

SERVICE_DESCRIPTION = ServiceDescriptor(SERVICE_AGENT, SERVICE_API, [],
                                        ExecutionMode.ANY, ServiceType.CONTROL,
                                        "Saturnin runtime node service",
                                        'saturnin.service.node.service:SaturninNodeServiceImpl',
                                        'saturnin.sdk.classic:SimpleService',
                                        'saturnin.service.node.client:SaturninNodeClient',
                                        'saturnin.service.node.test:TestRunner')

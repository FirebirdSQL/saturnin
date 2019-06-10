#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log service
# FILE:           saturnin/service/fblog/api.py
# DESCRIPTION:    API for Saturnin Firebird log service
# CREATED:        3.6.2019
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

"""Saturnin - Firebird log service API

Firebird log Service monitors firebird.log file and emits log events into data pipeline.

Supported requests:

    :MONITOR:     Starts contionuous monitoring of firebird.log file. New entries are parsed
                  and sent to data pipeline.
    :GET_ENTRIES: Send parsed (selected) entries from firebird.log as stream of DATA messages.
"""

from enum import IntEnum
from uuid import UUID, NAMESPACE_OID, uuid5
from saturnin.sdk import VENDOR_UID
from saturnin.sdk.types import AgentDescriptor, InterfaceDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType

SERVICE_OID: str = '1.3.6.1.4.1.53446.1.1.3' # firebird.butler.service.firebird-log
SERVICE_UID: UUID = uuid5(NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1'

# firebird.butler.service.firebird-log.interface
FBLOG_INTERFACE_OID: str = '1.3.6.1.4.1.53446.1.1.3.0'
FBLOG_INTERFACE_UID: UUID = uuid5(NAMESPACE_OID, FBLOG_INTERFACE_OID)

#  Enums (Request and Error Codes)

class FbLogRequest(IntEnum):
    "Saturnin Firebird Log Service Request Code"
    MONITOR = 1
    GET_ENTRIES = 2

class FbLogError(IntEnum):
    "Saturnin Firebird Log Service Error Code"
    ALREADY_RUNNING = 1
    RESOURCE_NOT_AVAILABLE = 2

#  Service description

SERVICE_AGENT = AgentDescriptor(SERVICE_UID,
                                "firebird-log",
                                SERVICE_VERSION,
                                VENDOR_UID,
                                "firebird/log",
                               )
SERVICE_INTERFACE = InterfaceDescriptor(FBLOG_INTERFACE_UID,
                                        "Saturnin Firebird Log service API", 1,
                                        FbLogRequest)
SERVICE_API = [SERVICE_INTERFACE]

SERVICE_DESCRIPTION = ServiceDescriptor(SERVICE_AGENT, SERVICE_API, [],
                                        ExecutionMode.ANY, ServiceType.DATA_PROVIDER,
                                        "Saturnin Firebird Log service",
                                        'saturnin.service.fblog.service:FirebirdLogServiceImpl',
                                        'saturnin.sdk.classic:SimpleService',
                                        'saturnin.service.fblog.client:FirebirdLogClient',
                                        'saturnin.service.fblog.test:TestRunner')

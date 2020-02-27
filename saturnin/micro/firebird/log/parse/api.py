#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/firebird/log/parse/api.py
# DESCRIPTION:    API for Firebird log parser microservice
# CREATED:        18.12.2019
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

"""Saturnin microservices - API for Firebird log parser microservice

This microservice is a DATA_FILTER that reads blocks of Firebird log text from input data
pipe, and sends parsed Firebird log entries into output data pipe.
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import MIME_TYPE_PROTO, AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities, Enum
from saturnin.core.config import create_config, MicroDataFilterConfig

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.firebird.log.parse
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.3.1.2'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

LOG_PROTO =  'saturnin.protobuf.fblog.LogEntry'
LOG_FORMAT = '%s;type=%s' % (MIME_TYPE_PROTO, LOG_PROTO)

# Enums

class Severity(Enum):
    """Firebird Log Message severity"""
    UNKNOWN = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class Facility(Enum):
    """Firebird Log Server facility"""
    UNKNOWN = 0
    SYSTEM = 1
    CONFIG = 2
    INTL = 3
    FILEIO = 4
    USER = 5
    VALIDATION = 6
    SWEEP = 7
    PLUGIN = 8
    GUARDIAN = 9
    NET = 10
    AUTH = 11

# Configuration

class FbLogParserConfig(MicroDataFilterConfig):
    """Firebird log parser microservice configuration"""
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.input_format.default = 'text/plain;charset=utf-8'
        self.input_format.set_value('text/plain;charset=utf-8')
        self.output_format.default = LOG_FORMAT
        self.output_format.set_value(LOG_FORMAT)

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name='firebird.saturnin.micro.firebird.log.parse',
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="firebird-log/parser")

SERVICE_DESCRIPTOR: ServiceDescriptor = \
    ServiceDescriptor(agent=SERVICE_AGENT,
                      api=[],
                      dependencies=[],
                      execution_mode=ExecutionMode.THREAD,
                      service_type=ServiceType.DATA_PROVIDER,
                      facilities=(ServiceFacilities.INPUT_AS_CLIENT |
                                  ServiceFacilities.INPUT_AS_SERVER |
                                  ServiceFacilities.OUTPUT_AS_CLIENT |
                                  ServiceFacilities.OUTPUT_AS_SERVER),
                      description="Firebird log parser microservice",
                      implementation='saturnin.micro.firebird.log.parse.service:FbLogParserImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, FbLogParserConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Firebird log parser microservice"),
                      client=None,
                      tests=None)

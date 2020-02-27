#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/reader/api.py
# DESCRIPTION:    API for Text file reader microservice
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

"""Saturnin microservices - API for Text file reader microservice

This microservice is a DATA_PROVIDER that sends blocks of text from file to output data pipe.
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities
from saturnin.core.config import create_config, MicroDataFilterConfig, MIMEOption, \
     StrOption, IntOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.text.reader
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.1.1'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

# Configuration

class TextReaderConfig(MicroDataFilterConfig):
    "Text file reader microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.file: StrOption = StrOption('file', "File specification", required=True)
        self.file_format: MIMEOption = \
            MIMEOption('file_format', "File data format specification", required=True,
                       default='text/plain;charset=utf-8')
        self.max_chars: IntOption = \
            IntOption('max_chars',
                      "Max. number of characters transmitted in one message",
                      required=True, default=65535)

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.text.reader",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="text/reader")

SERVICE_DESCRIPTOR: ServiceDescriptor = \
    ServiceDescriptor(agent=SERVICE_AGENT,
                      api=[],
                      dependencies=[],
                      execution_mode=ExecutionMode.THREAD,
                      service_type=ServiceType.DATA_PROVIDER,
                      facilities=(ServiceFacilities.OUTPUT_AS_CLIENT |
                                  ServiceFacilities.OUTPUT_AS_SERVER),
                      description="Text reader microservice",
                      implementation='saturnin.micro.text.reader.service:MicroTextReaderImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, TextReaderConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Text Reader microservice"),
                      client=None,
                      tests=None)
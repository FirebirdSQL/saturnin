#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/writer/api.py
# DESCRIPTION:    API for Text file writer microservice
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

"""Saturnin microservices - API for Text file writer microservice

This microservice is a DATA_CONSUMER that wites blocks of text from input data pipe to file.
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities, FileOpenMode, SaturninError
from saturnin.core.config import create_config, MicroDataConsumerConfig, MIMEOption, \
     StrOption, EnumOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.text.writer
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.1.2'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

# Configuration

class TextWriterConfig(MicroDataConsumerConfig):
    "Text file writer microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.file: StrOption = StrOption('file', "File specification", required=True)
        self.file_format: MIMEOption = \
            MIMEOption('file_format', "File data format specification",
                       required=True, default='text/plain;charset=utf-8')
        self.file_mode: EnumOption = \
            (EnumOption('file_mode', FileOpenMode, "File I/O mode", required=False))
    def validate(self) -> None:
        "Extended validation"
        super().validate()
        if (self.file.value.lower() in ['stdout', 'stderr'] and
            self.file_mode.value != FileOpenMode.WRITE):
            raise SaturninError("STD[OUT|ERR] support only WRITE open mode")
        if self.file_mode.value not in (FileOpenMode.APPEND, FileOpenMode.CREATE,
                                        FileOpenMode.RENAME, FileOpenMode.WRITE):
            raise SaturninError("File open mode '%' not supported" % self.file_mode.value.name)
        if self.file_format.mime_type != 'text/plain':
            raise SaturninError("Only 'text/plain' file format supported")

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.text.writer",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="text/writer")

SERVICE_DESCRIPTOR: ServiceDescriptor = \
    ServiceDescriptor(agent=SERVICE_AGENT,
                      api=[],
                      dependencies=[],
                      execution_mode=ExecutionMode.THREAD,
                      service_type=ServiceType.DATA_CONSUMER,
                      facilities=(ServiceFacilities.INPUT_AS_CLIENT |
                                  ServiceFacilities.INPUT_AS_SERVER),
                      description="Text writer microservice",
                      implementation='saturnin.micro.text.writer.service:MicroTextWriterImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, TextWriterConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Text writer microservice"),
                      client=None,
                      tests=None)

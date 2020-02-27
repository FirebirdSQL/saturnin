#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/printer/api.py
# DESCRIPTION:    API for Data printer microservice
# CREATED:        5.1.2020
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

"""Saturnin microservices - API for Data printer microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses formatting template and data from protobuf message to create text
- OUTPUT: blocks of text
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import MIME_TYPE_TEXT, MIME_TYPE_PROTO, AgentDescriptor, \
     ServiceDescriptor, ExecutionMode, ServiceType, ServiceFacilities,SaturninError
from saturnin.core.config import create_config, MicroDataFilterConfig, StrOption, \
     IntOption, PyCallableOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.data.printer
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.2.3'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

# Configuration

class DataPrinterConfig(MicroDataFilterConfig):
    "Data printer microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.output_format.default = 'text/plain;charset=utf-8'
        self.output_format.set_value('text/plain;charset=utf-8')
        #
        self.template: StrOption = \
            StrOption('template', "Text formatting template")
        self.func: PyCallableOption = \
            PyCallableOption('func',
                             "Function that returns text representation of data",
                             'data, utils')
    def validate(self) -> None:
        """Checks:
    - whether all required options have value other than None
    - that 'input_format' MIME type is 'text/plain'
    - that 'output_format' MIME type is 'application/x.fb.proto'
    - that exactly one from 'func' or 'template' options have a value
    - that 'func' option value could be compiled

Raises:
    SaturninError: When any check fails
"""
        super().validate()
        #
        if self.output_format.mime_type != MIME_TYPE_TEXT:
            raise SaturninError(f"Only '{MIME_TYPE_TEXT}' output format allowed.")
        if self.input_format.mime_type != MIME_TYPE_PROTO:
            raise SaturninError(f"Only '{MIME_TYPE_PROTO}' input format allowed.")
        #
        defined = 0
        for opt in (self.template, self.func):
            if opt.value is not None:
                defined += 1
        if defined != 1:
            raise SaturninError("Configuration must contain either 'template' or 'func' option")
        #
        try:
            self.func.get_callable()
        except Exception as exc:
            raise SaturninError("Invalid code definition in 'func' option") from exc


# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.data.printer",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="data/printer")

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
                      description="Data printer microservice",
                      implementation='saturnin.micro.data.printer.service:MicroDataPrinterImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, DataPrinterConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Data printer microservice"),
                      client=None,
                      tests=None)

#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log microservice
# FILE:           saturnin/micro/fblog/api.py
# DESCRIPTION:    API for FBLOG microservice
# CREATED:        13.9.2019
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

"""Saturnin - API for firebird-log microservice

The FBLOG microservice can perform the following operations with Firebird Server log,
depending on the configuration:

LOG_FROM_SERVER - Pipe OUTPUT: Text log obtained from Firebird server via FB service manager
PARSE_LOG       - Pipe INPUT: Text log, Pipe OUTPUT: Parsed log
FILTER_PARSED   - Pipe INPUT: Parsed log, Pipe OUTPUT: Filtered parsed log
PRINT_PARSED    - Pipe INPUT: Parsed log, Pipe OUTPUT: Text log
"""

import uuid
from functools import partial, reduce
from saturnin.sdk import VENDOR_UID
from saturnin.sdk.types import Enum, AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities, SocketMode
from saturnin.sdk.config import create_config, MicroserviceConfig, StrOption, EnumOption, \
     IntOption, BoolOption, ZMQAddressOption, MIMEOption, Option

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.firebird-log
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.2'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1'

# Enums

class FbLogOperation(Enum):
    "Operations implemented by FBLOG microservice"
    LOG_FROM_SERVER = Enum.auto()
    PARSE_LOG = Enum.auto()
    FILTER_PARSED = Enum.auto()
    PRINT_PARSED = Enum.auto()

# Configuration

class FbLogConfig(MicroserviceConfig):
    "TextIO service configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.operation: EnumOption = \
            self.add_option(EnumOption('operation', FbLogOperation,
                                       "Operation to perform", required=True))
        self.stop_on_close: BoolOption = \
            self.add_option(BoolOption('stop_on_close', "Stop service when pipe is closed",
                                       default=True))
        self.input_pipe: StrOption = \
            self.add_option(StrOption('input_pipe', "Input Data Pipe Identification"))
        self.input_address: ZMQAddressOption = \
            self.add_option(ZMQAddressOption('input_address', "Input Data Pipe endpoint address"))
        self.input_mode: EnumOption = \
            self.add_option(EnumOption('input_mode', SocketMode, "Input Data Pipe Mode",
                                       default=SocketMode.CONNECT))
        self.input_format: MIMEOption = \
            self.add_option(MIMEOption('input_format', "Input Pipe data format specification"))
        self.input_batch_size: IntOption = \
            self.add_option(IntOption('input_batch_size', "Input data batch size",
                                      default=50))
        self.output_pipe: StrOption = \
            self.add_option(StrOption('output_pipe', "Output Data Pipe Identification",
                                      required=True))
        self.output_address: ZMQAddressOption = \
            self.add_option(ZMQAddressOption('output_address', "Output Data Pipe endpoint address",
                                             required=True))
        self.output_mode: EnumOption = \
            self.add_option(EnumOption('output_mode', SocketMode, "Output Data Pipe Mode",
                                       required=True, default=SocketMode.CONNECT))
        self.output_format: MIMEOption = \
            self.add_option(MIMEOption('output_format', "Output Pipe data format specification"))
        self.output_batch_size: IntOption = \
            self.add_option(IntOption('output_batch_size', "Output data batch size",
                                      required=True, default=50))
        self.print_format: StrOption = \
            self.add_option(StrOption('print_format', "Format for 'print_parsed' operation",
                                      default='%(origin)s %(timestamp)s [%(level)s] [%(code)s] : %(message)s'))
        self.user: StrOption = \
            self.add_option(StrOption('user', "Firebird user name", default='SYSDBA'))
        self.password: StrOption = \
            self.add_option(StrOption('password', "Firebird user password", default='masterkey'))
        self.filter_expr: StrOption = \
            self.add_option(StrOption('filter_expr', "Filter expression"))
    def __fail(self, msg: str) -> None:
        raise ValueError(msg % self.operation.value.name)
    def __ensure_input(self) -> None:
        if not reduce(lambda res, opt: res and opt is not None,
                      [self.input_pipe, self.input_mode, self.input_address,
                       self.input_batch_size], True):
            self.__fail("Input pipe specification required for operation %s")
    def __ensure_format(self, opt: MIMEOption, fmt: str, direction: str):
        if opt.value and opt.mime_type != fmt:
            raise ValueError("Only '%s' %s format is supported for operation %s"
                             % (fmt, direction, self.operation.value.name))
    def __ensure_required(self, opt: Option) -> None:
        opt.required = True
        opt.validate()
    def validate(self) -> None:
        "Extended validation"
        super().validate()
        if self.operation.value == FbLogOperation.LOG_FROM_SERVER:
            if self.input_pipe.value is not None:
                self.__fail("Input pipe specification not allowed for operation %s")
            self.__ensure_format(self.output_format, 'text/plain', 'output')
            self.__ensure_required(self.user)
            self.__ensure_required(self.password)
        elif self.operation.value == FbLogOperation.PARSE_LOG:
            self.__ensure_input()
            self.__ensure_format(self.input_format, 'text/plain', 'input')
            self.__ensure_format(self.output_format, 'application/x.fb.proto', 'output')
        elif self.operation.value == FbLogOperation.FILTER_PARSED:
            self.__ensure_input()
            self.__ensure_format(self.input_format, 'application/x.fb.proto', 'input')
            self.__ensure_format(self.output_format, 'application/x.fb.proto', 'output')
            self.__ensure_required(self.filter_expr)
        elif self.operation.value == FbLogOperation.PRINT_PARSED:
            self.__ensure_input()
            self.__ensure_format(self.input_format, 'application/x.fb.proto', 'input')
            self.__ensure_format(self.output_format, 'text/plain', 'output')
            self.__ensure_required(self.print_format)

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird-log",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="firebird/server-log")

SERVICE_DESCRIPTION: ServiceDescriptor = \
    ServiceDescriptor(agent=SERVICE_AGENT,
                      api=[],
                      dependencies=[],
                      execution_mode=ExecutionMode.THREAD,
                      service_type=ServiceType.DATA_FILTER,
                      facilities=(ServiceFacilities.INPUT_CLIENT | ServiceFacilities.INPUT_SERVER |
                                  ServiceFacilities.OUTPUT_CLIENT | ServiceFacilities.OUTPUT_SERVER),
                      description="Microservice for operations with Firebird Server log",
                      implementation='saturnin.micro.fblog.service:FbLogServiceImpl',
                      container='saturnin.sdk.classic:SimpleService',
                      config=partial(create_config, FbLogConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "FBLOG microservice"),
                      client=None,
                      tests=None)

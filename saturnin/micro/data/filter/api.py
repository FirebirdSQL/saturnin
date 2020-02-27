#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/filter/api.py
# DESCRIPTION:    API for Data filter microservice
# CREATED:        20.1.2020
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

"""Saturnin microservices - API for Data filter microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses expressions / functions evaluating data from protobuf message to filter data for output
- OUTPUT: protobuf messages
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import MIME_TYPE_PROTO, AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities,SaturninError
from saturnin.core.config import create_config, MicroDataFilterConfig, PyExprOption, \
     PyCallableOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.data.filter
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.2.4'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

# Configuration

class DataFilterConfig(MicroDataFilterConfig):
    "Data filter microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.include_expr: PyExprOption = \
            PyExprOption('include_expr', "Data inclusion Python expression")
        self.include_func: PyCallableOption = \
            PyCallableOption('include_func', "Data inclusion Python function", 'data')
        self.exclude_expr: PyExprOption = \
            PyExprOption('exclude_expr', "Data exclusion Python expression")
        self.exclude_func: PyCallableOption = \
            PyCallableOption('exclude_func', "Data exclusion Python function", 'data')
    def validate(self) -> None:
        """Checks:
    - whether all required options have value other than None.
    - that input/output MIME type is MIME_TYPE_PROTO
    - that input and output MIME 'type' params are present and the same
    - that at least one from '*_func' / '*_expr' options have a value
    - that only one from include / exclude methods is defined
    - that '*_func' option value could be compiled

Raises:
    SaturninError: When any check fails
"""
        super().validate()
        #
        for fmt in [self.output_format, self.input_format]:
            if fmt.mime_type != MIME_TYPE_PROTO:
                raise SaturninError(f"Only '{MIME_TYPE_PROTO}' format allowed for '{fmt.name}' option.")
            if not fmt.get_param('type'):
                raise SaturninError(f"The 'type' parameter not found in '{fmt.name}' option.")
        #
        if self.output_format.get_param('type') != self.input_format.get_param('type'):
            raise SaturninError(f"The 'type' parameter value must be the same for both MIME format options.")
        #
        defined = 0
        for opt in [self.include_func, self.exclude_func, self.include_expr, self.exclude_expr]:
            if opt.value is not None:
                defined += 1
        if defined == 0:
            raise SaturninError("At least one filter specification option must have a value")
        #
        for expr, func in [(self.include_func, self.include_expr),
                           (self.exclude_func, self.exclude_expr)]:
            if expr.value and func.value:
                raise SaturninError(f"Options '{expr.name}' and '{func.name}' are mutually exclusive")
        #
        for func in [self.include_func, self.exclude_func]:
            try:
                func.get_callable()
            except Exception as exc:
                raise SaturninError(f"Invalid code definition in '{func.name}' option") from exc


# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.data.filter",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="data/filter")

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
                      description="Data filter microservice",
                      implementation='saturnin.micro.data.filter.service:MicroPBDataFilterImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, DataFilterConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Data filter microservice"),
                      client=None,
                      tests=None)

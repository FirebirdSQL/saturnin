#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/filter/api.py
# DESCRIPTION:    API for Data aggregator microservice
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

"""Saturnin microservices - API for Data aggregator microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses expressions / functions evaluating data from protobuf message to aggregate data for output
- OUTPUT: protobuf messages
"""

import uuid
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import MIME_TYPE_PROTO, AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities,SaturninError
from saturnin.core.config import create_config, MicroDataFilterConfig, ListOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.data.aggregator
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.2.5'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

AGGREGATE_PROTO =  'saturnin.protobuf.GenDataRecord'
AGGREGATE_FORMAT = '%s;type=%s' % (MIME_TYPE_PROTO, AGGREGATE_PROTO)

AGGREGATE_FUNCTIONS = ['count', 'min', 'max', 'sum', 'avg']

# Configuration

class DataAggregatorConfig(MicroDataFilterConfig):
    "Data aggregator microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.group_by: ListOption = \
            ListOption('group_by', "Specification of fields that are 'group by' key",
                       required=True)
        self.aggregate: ListOption = \
            ListOption('aggregate', "Specification for aggregates", required=True)
        #
        self.output_format.default = AGGREGATE_FORMAT
        self.output_format.set_value(AGGREGATE_FORMAT)
    def validate(self) -> None:
        """Checks:
    - whether all required options have value other than None.
    - that 'input_format' MIME type is 'application/x.fb.proto'
    - that 'output_format' MIME type is 'application/x.fb.proto;type=saturnin.protobuf.common.GenDataRecord'
    - that 'aggregate' values have format '<aggregate_func>:<field_spec>', and
      <aggregate_func> is from supported functions

Raises:
    SaturninError: When any check fails
"""
        super().validate()
        #
        if self.input_format.mime_type != MIME_TYPE_PROTO:
            raise SaturninError(f"Only '{MIME_TYPE_PROTO}' input format allowed.")
        if self.output_format.value != AGGREGATE_FORMAT:
            raise SaturninError(f"Only '{AGGREGATE_FORMAT}' output format allowed.")
        #
        for spec in self.aggregate.value:
            l = spec.split(':')
            if len(l) != 2:
                raise SaturninError("The 'aggregate' values must have '<aggregate_func>:<field_spec>' format")
            func_name = l[0].lower()
            if ' as ' in func_name:
                func_name, _ = func_name.split(' as ')
            if func_name not in AGGREGATE_FUNCTIONS:
                raise SaturninError(f"Unknown aggregate function '{func_name}'")

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.data.aggregator",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="data/aggregator")

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
                      description="Data aggregator microservice",
                      implementation='saturnin.micro.data.aggregator.service:MicroDataAggregatorImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, DataAggregatorConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Data aggregator microservice"),
                      client=None,
                      tests=None)

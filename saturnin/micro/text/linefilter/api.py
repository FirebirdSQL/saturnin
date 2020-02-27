#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/linefilter/api.py
# DESCRIPTION:    API for Text line filter microservice
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

"""Saturnin microservices - API for Text line filter microservice

This microservice is a DATA_FILTER that reads blocks of text from input data pipe, and
writes lines that meet the specified conditions as blocks of text into output data pipe.
"""

import uuid
import re
from functools import partial
from saturnin.core import VENDOR_UID
from saturnin.core.types import AgentDescriptor, ServiceDescriptor, \
     ExecutionMode, ServiceType, ServiceFacilities, SaturninError
from saturnin.core.config import create_config, MicroDataFilterConfig, \
     StrOption, IntOption, PyExprOption, PyCallableOption

# OID: iso.org.dod.internet.private.enterprise.firebird.butler.microservice.text.linefilter
SERVICE_OID: str = '1.3.6.1.4.1.53446.1.6.1.3'
SERVICE_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, SERVICE_OID)
SERVICE_VERSION: str = '0.1.0'

# Configuration

class TextReaderConfig(MicroDataFilterConfig):
    "Text line filter microservice configuration"
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        #
        self.max_chars: IntOption = \
            IntOption('max_chars',
                      "Max. number of characters transmitted in one message",
                      required=True, default=65535)
        self.regex: StrOption = StrOption('regex', "Regular expression")
        self.expr: PyExprOption = PyExprOption('expr', "Python expression")
        self.func: PyCallableOption = PyCallableOption('func', "Python function",
                                                       'line')
    def validate(self) -> None:
        """Checks whether all required options have value other than None.

Raises:
    Error: When required option does not have a value.
"""
        super().validate()
        defined = 0
        for opt in (self.regex, self.expr, self.func):
            if opt.value is not None:
                defined += 1
        if defined != 1:
            raise SaturninError("Configuration must contain exactly one filter definition.")
        #
        if self.regex.value is not None:
            re.compile(self.regex.value)
        try:
            self.func.get_callable()
        except Exception as exc:
            raise SaturninError("Invalid code definition in 'func' option") from exc

# Service description

SERVICE_AGENT: AgentDescriptor = \
    AgentDescriptor(uid=SERVICE_UID,
                    name="firebird.saturnin.micro.text.linefilter",
                    version=SERVICE_VERSION,
                    vendor_uid=VENDOR_UID,
                    classification="text/linefilter")

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
                      description="Text line filter microservice",
                      implementation='saturnin.micro.text.linefilter.service:MicroTextFilterImpl',
                      container='saturnin.core.classic:SimpleService',
                      config=partial(create_config, TextReaderConfig,
                                     '%s_service' % SERVICE_AGENT.name,
                                     "Text line filter microservice"),
                      client=None,
                      tests=None)

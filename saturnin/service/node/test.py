#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service
# FILE:           saturnin/service/node/test.py
# DESCRIPTION:    Test runner for NODE service (classic version)
# CREATED:        13.5.2019
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

"""Test runner for NODE service (classic version)
"""

from uuid import uuid1
from saturnin.sdk.types import TClient, TChannel
from saturnin.sdk.fbsptest import BaseTestRunner, zmq, print_msg
from saturnin.service.node.api import SaturninNodeRequest, NODE_INTERFACE_UID
from saturnin.protobuf import node_pb2 as pb
from saturnin.service.node.client import SaturninNodeClient
from saturnin.sdk.types import MsgType
import saturnin.service.roman.api as roman_api

class TestRunner(BaseTestRunner):
    """Test Runner for ROMAN Service and Client.
"""
    def __init__(self, context):
        super().__init__(context)
        self.interface_uid = NODE_INTERFACE_UID.bytes
    def create_client(self, channel: TChannel) -> TClient:
        return SaturninNodeClient(channel, self.peer, self.agent)
    def run_request(self, api_call):
        "Execute Client API call."
        print('Sent:')
        data = api_call()
        print('Received:')
    def raw_installed_services(self, socket: zmq.Socket):
        "Raw test of INSTALLED_SERVICES request."
        print("Sending INSTALLED_SERVICES request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               SaturninNodeRequest.INSTALLED_SERVICES,
                                               self.get_token())
        print_msg(msg)
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        dframe = pb.ReplyInstalledServices()
        dframe.ParseFromString(msg.data[0])
        print_msg(msg, str(dframe))
    def raw_interface_providers(self, socket: zmq.Socket):
        "Raw test of INTERFACE_PROVIDERS request."
        print("Sending INTERFACE_PROVIDERS request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               SaturninNodeRequest.INTERFACE_PROVIDERS,
                                               self.get_token())
        dframe = pb.RequestInterfaceProviders()
        dframe.interface_uid = NODE_INTERFACE_UID.bytes
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        dframe = pb.ReplyInterfaceProviders()
        dframe.ParseFromString(msg.data[0])
        print_msg(msg, str(dframe))
    def raw_start_service(self, socket: zmq.Socket):
        "Raw test of START_SERVICE request."
        print("Sending START_SERVICE request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               SaturninNodeRequest.START_SERVICE,
                                               self.get_token())
        dframe = pb.RequestStartService()
        dframe.agent_uid = roman_api.SERVICE_UID.bytes
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        if msg.message_type == MsgType.REPLY:
            dframe = pb.ReplyStartService()
            dframe.ParseFromString(msg.data[0])
        elif msg.message_type == MsgType.ERROR:
            dframe = ''
        print_msg(msg, str(dframe))
    #def client_installed_services(self, client: TClient):
        #"Client test of get_installed() API call."
        #self.run_request(client.get_installed)

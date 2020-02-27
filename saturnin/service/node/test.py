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

from uuid import UUID
import zmq
from saturnin.sdk.types import ZMQAddress
from saturnin.sdk.base import Channel
from saturnin.sdk.test.fbsp import MsgType, BaseTestRunner, print_msg, print_title, \
     print_data
from saturnin.sdk.config import ServiceConfig
from . import node_pb2 as pb
from .api import NodeRequest, NODE_INTERFACE_UID
from .client import SaturninNodeClient
import saturnin.service.roman.api as roman_api

class TestRunner(BaseTestRunner):
    """Test Runner for NODE Service and Client.
"""
    def __init__(self, context):
        super().__init__(context)
        self.interface_uid = NODE_INTERFACE_UID.bytes
        self.peer_uid = None
    def create_client(self, channel: Channel) -> SaturninNodeClient:
        return SaturninNodeClient(channel, self.peer, self.agent)
    def run_request(self, api_call, *args, **kwargs):
        "Execute Client API call."
        print('Sending request..')
        try:
            data = api_call(*args, **kwargs)
            print('Received:')
            print_data(data)
            return data
        except Exception as exc:
            print_title("ERROR", char="*")
            print(exc)
    def raw_01_installed_services(self, socket: zmq.Socket):
        "Raw test of INSTALLED_SERVICES request."
        print("Sending INSTALLED_SERVICES request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.INSTALLED_SERVICES,
                                               self.get_token())
        print_msg(msg)
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        dframe = pb.ReplyInstalledServices()
        dframe.ParseFromString(msg.data[0])
        print_msg(msg, str(dframe))
    def raw_02_interface_providers(self, socket: zmq.Socket):
        "Raw test of INTERFACE_PROVIDERS request."
        print("Sending INTERFACE_PROVIDERS request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.INTERFACE_PROVIDERS,
                                               self.get_token())
        dframe = pb.RequestInterfaceProviders()
        dframe.interface_uid = roman_api.ROMAN_INTERFACE_UID.bytes
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        dframe = pb.ReplyInterfaceProviders()
        dframe.ParseFromString(msg.data[0])
        print_msg(msg, str(dframe))
        for agent_uid in dframe.agent_uids:
            if UUID(bytes=agent_uid) == roman_api.SERVICE_UID:
                print("    The reply is correct")
                return
    def raw_03_start_service(self, socket: zmq.Socket):
        "Raw test of START_SERVICE request."
        print("Sending START_SERVICE request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.START_SERVICE,
                                               self.get_token())
        dframe: pb.RequestStartService = pb.RequestStartService()
        dframe.agent_uid = roman_api.SERVICE_UID.bytes
        cfg: ServiceConfig = roman_api.SERVICE_DESCRIPTOR.config()
        cfg.endpoints.set_value([ZMQAddress('tcp://127.0.0.1:7001')])
        cfg.save_proto(dframe.config)
        dframe.name = 'roman-test'
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        if msg.message_type == MsgType.REPLY:
            dframe = pb.ReplyStartService()
            dframe.ParseFromString(msg.data[0])
            self.peer_uid = dframe.service.peer.uid
            data = str(dframe)
        elif msg.message_type == MsgType.ERROR:
            data = None
        print_msg(msg, data)
    def raw_04_running_services(self, socket: zmq.Socket):
        "Raw test of RUNNING_SERVICES request."
        print("Sending RUNNING_SERVICES request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.RUNNING_SERVICES,
                                               self.get_token())
        print_msg(msg)
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        dframe = pb.ReplyRunningServices()
        dframe.ParseFromString(msg.data[0])
        print_msg(msg, str(dframe))
    def raw_05_stop_service(self, socket: zmq.Socket):
        "Raw test of STOP_SERVICE request."
        if not self.peer_uid:
            print_title("TEST SKIPPED", char='*')
            return
        print("Sending STOP_SERVICE request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.STOP_SERVICE,
                                               self.get_token())
        dframe = pb.RequestStopService()
        dframe.peer_uid = self.peer_uid
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        if msg.message_type == MsgType.REPLY:
            dframe = pb.ReplyStopService()
            dframe.ParseFromString(msg.data[0])
            data = str(dframe)
        elif msg.message_type == MsgType.ERROR:
            data = None
        print_msg(msg, data)
    def raw_06_shutdown(self, socket: zmq.Socket):
        "Raw test of SHUTDOWN request."
        print("Sending SHUTDOWN request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.SHUTDOWN,
                                               self.get_token())
        print_msg(msg, None)
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        print_msg(msg, None)
    def client_01_installed_services(self, client: SaturninNodeClient):
        "Client test of get_installed() API call."
        self.run_request(client.get_installed)
    def client_02_interface_providers(self, client: SaturninNodeClient):
        "Client test of get_providers() API call."
        self.run_request(client.get_providers, roman_api.ROMAN_INTERFACE_UID)
    def client_03_start_service(self, client: SaturninNodeClient):
        "Client test of start_service() API call."
        cfg: ServiceConfig = roman_api.SERVICE_DESCRIPTOR.config()
        cfg.endpoints.set_value([ZMQAddress('tcp://127.0.0.1:*')])
        data = self.run_request(client.start_service, roman_api.SERVICE_UID, cfg)
        self.peer_uid = UUID(bytes=data.service.peer.uid)
    def client_04_running_services(self, client: SaturninNodeClient):
        "Client test of get_running() API call."
        self.run_request(client.get_running)
    def client_05_stop_service(self, client: SaturninNodeClient):
        "Client test of stop_service() API call."
        self.run_request(client.stop_service, self.peer_uid)
    def client_06_shutdown(self, client: SaturninNodeClient):
        "Client test of get_running() API call."
        self.run_request(client.shutdown)

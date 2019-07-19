#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log service
# FILE:           saturnin/service/fblog/test.py
# DESCRIPTION:    Test runner for Firebird log service (classic version)
# CREATED:        3.6.2019
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

"""Test runner for Firebird log service (classic version)
"""

#from uuid import UUID
from tempfile import gettempdir
from os import remove
import os.path
from time import sleep
from saturnin.sdk.types import MsgType, TClient, TChannel, ClientError
from saturnin.sdk.fbsptest import BaseTestRunner, zmq, print_msg, print_title, print_data
from saturnin.protobuf import fblog_pb2 as pb
from .api import FbLogRequest, FBLOG_INTERFACE_UID
from .client import FirebirdLogClient

class TestRunner(BaseTestRunner):
    """Test Runner for Firebird log Service and Client.
"""
    def __init__(self, context):
        super().__init__(context)
        self.interface_uid = FBLOG_INTERFACE_UID.bytes
        self.peer_uid = None
    def create_client(self, channel: TChannel) -> TClient:
        return FirebirdLogClient(channel, self.peer, self.agent)
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
    #def raw_01_imonitor(self, socket: zmq.Socket):
        #"Raw test of MONITOR request."
        #print("Sending MONITOR request:")
        #msg = self.protocol.create_request_for(self.interface_id,
                                               #FbLogRequest.MONITOR,
                                               #self.get_token())
        #dframe = pb.RequestMonitor()
        #msg.data.append(dframe.SerializeToString())
        #print_msg(msg)
        #socket.send_multipart(msg.as_zmsg())
        #print("Receiving reply:")
        #zmsg = socket.recv_multipart()
        #msg = self.protocol.parse(zmsg)
        #dframe = pb.ReplyMonitor()
        #dframe.ParseFromString(msg.data[0])
        #print_msg(msg, str(dframe))
    #def raw_02_stop_monitor(self, socket: zmq.Socket):
        #"Raw test of STOP_MONITOR request."
        #print("Sending STOP_MONITOR request:")
        #msg = self.protocol.create_request_for(self.interface_id,
                                               #FbLogRequest.STOP_MONITOR,
                                               #self.get_token())
        #dframe = pb.RequestStopMonitor()
        #msg.data.append(dframe.SerializeToString())
        #print_msg(msg, str(dframe))
        #socket.send_multipart(msg.as_zmsg())
        #print("Receiving reply:")
        #zmsg = socket.recv_multipart()
        #msg = self.protocol.parse(zmsg)
        #dframe = pb.ReplyInterfaceProviders()
        #dframe.ParseFromString(msg.data[0])
        #print_msg(msg, str(dframe))
    def raw_03_entries(self, socket: zmq.Socket):
        "Raw test of ENTRIES request."
        #tempfile = os.path.join(gettempdir(), 'fblog-testlog.tmp')
        #logfile = open(tempfile, mode = "w")
        #logfile.writelines(["machine (Client)	Fri Jul 12 17:55:43 2019\n",
                            #"\t/opt/firebird/bin/fbguard: guardian starting /opt/firebird/bin/fbserver\n",
                            #"\n\n\n",
                            #"machine (Client)	Sat Jul 13 10:51:56 2019\n",
                            #"\t/opt/firebird/bin/fbguard: guardian starting /opt/firebird/bin/fbserver\n",
                            #"\n\n\n",
                            #"machine (Client)	Sat Jul 13 14:19:08 2019\n"
                            #"\t/opt/firebird/bin/fbguard: /opt/firebird/bin/fbserver normal shutdown.\n"
                            #"\n\n\n"
                            #])
        #logfile.close()
        #try:
        #tempfile = '/opt/firebird/firebird.log'
        tempfile = '/home/job/python/projects/saturnin/fblog-test.log'
        print("Sending ENTRIES request:")
        msg = self.protocol.create_request_for(self.interface_id,
                                               FbLogRequest.ENTRIES,
                                               self.get_token())
        dframe = pb.RequestEntries()
        dframe.source.filespec = tempfile
        msg.data.append(dframe.SerializeToString())
        print_msg(msg, str(dframe))
        socket.send_multipart(msg.as_zmsg())
        print("Receiving reply:")
        zmsg = socket.recv_multipart()
        msg = self.protocol.parse(zmsg)
        if msg.message_type == MsgType.REPLY:
            data = str(dframe)
        elif msg.message_type == MsgType.ERROR:
            data = None
        print_msg(msg, data)
        if msg.has_ack_req():
            print("Sending ACK reply.")
            reply = self.protocol.create_ack_reply(msg)
            socket.send_multipart(reply.as_zmsg())
        log_entry = pb.FirebirdLogEntry()
        stop = False
        receive_cnt = 0
        msg_cnt = 0
        while not stop:
            if receive_cnt == 0:
                cnt = input('How many messages should be received?')
                if cnt.isnumeric():
                    receive_cnt = int(cnt)
                else:
                    receive_cnt = 1
            msg_cnt += 1
            print("Receiving [%s]:" % msg_cnt)
            event = socket.poll(5000)
            if event != 0:
                zmsg = socket.recv_multipart()
                receive_cnt -= 1
                msg = self.protocol.parse(zmsg)
                if msg.message_type == MsgType.DATA:
                    log_entry.ParseFromString(msg.data[0])
                    data = str(log_entry)
                elif msg.message_type == MsgType.STATE:
                    data = None
                    stop = True
                elif msg.message_type == MsgType.ERROR:
                    data = None
                    stop = True
                print_msg(msg, data)
            else:
                raise ClientError("Service did not respond in time.")
        #finally:
            #remove(tempfile)
        #def client_01_installed_services(self, client: TClient):
        #"Client test of get_installed() API call."
        #self.run_request(client.get_installed)
    #def client_02_interface_providers(self, client: TClient):
        #"Client test of get_providers() API call."
        #self.run_request(client.get_providers, roman_api.ROMAN_INTERFACE_UID)
    #def client_03_start_service(self, client: TClient):
        #"Client test of start_service() API call."
        #data = self.run_request(client.start_service, roman_api.SERVICE_UID)
        #self.peer_uid = UUID(bytes=data.peer_uid)

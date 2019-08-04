#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log service
# FILE:           saturnin/service/fblog/service.py
# DESCRIPTION:    Firebird log service (classic version)
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

"""Firebird log service (classic version)

Firebird log Service monitors firebird.log file and emits log events into data pipeline.

Supported requests:

    :MONITOR:      Starts contionuous monitoring of firebird.log file. New entries are parsed
                   and sent to data pipeline.
    :STOP_MONITOR: Stops contionuous monitoring of firebird.log file previously started by
                   MONITOR request.
    :ENTRIES:      Sends parsed (selected) entries from firebird.log as stream of DATA messages.
"""

import logging
from typing import Optional, Any, Dict, List, Callable, Iterable
from uuid import uuid1, UUID
import ctypes
import threading
import multiprocessing
from datetime import datetime
from functools import reduce
import zmq
from firebird.butler import fbsd_pb2 as fbsd
from saturnin.sdk.types import ServiceError, TMessage, TService, TServiceImpl, \
     TSession, TChannel, ZMQAddress, Origin, State, SocketType, \
     SocketUse, ExecutionMode, AddressDomain
from saturnin.sdk.base import BaseService, BaseMessageHandler, RouterChannel
from saturnin.sdk.service import SimpleServiceImpl
from saturnin.sdk.fbsp import MsgType, ErrorCode, MsgFlag, ServiceMessagelHandler, \
     HelloMessage, CancelMessage, RequestMessage, bb2h, note_exception
from saturnin.service.fblog.api import FbLogRequest, SERVICE_AGENT, SERVICE_API
from . import fblog_pb2 as pb
import fdb

# Logger

log = logging.getLogger(__name__)

class ParseError(Exception):
    "Exception raised on Firebird log parsing error"

# Constants

EOF = b'EOF'
TERMINATED = b'TERMINATED'

#  Functions

_PROTOCOL_MAP = dict((value, key) for key, value in fbsd.TransportProtocolEnum.items())

def toZMQAddress(endpoint: fbsd.EndpointAddress) -> ZMQAddress:
    "Converts protobuf saturnin.EndpointAddress to ZMQAddress"
    return ZMQAddress('%s://%s' % (_PROTOCOL_MAP[endpoint.protocol].lower(), endpoint.address))

def get_best_endpoint(endpoints: Iterable[ZMQAddress], host1: str, pid1: int,
                      host2: str, pid2: int) -> Optional[ZMQAddress]:
    "Returns endpoint that uses the best protocol from available options."
    local_addr = [x for x in endpoints if x.domain == AddressDomain.LOCAL]
    if (local_addr and host1 == host2 and pid1 == pid2):
        return local_addr[0]
    node_addr = [x for x in endpoints if x.domain == AddressDomain.NODE]
    if node_addr and (node_addr and host1 == host2):
        return node_addr[0]
    net_addr = [x for x in endpoints if x.domain == AddressDomain.NETWORK]
    if net_addr:
        return net_addr[0]
    return None

def parse_log(lines):
    "Parses the Firebird log and yields tuples with parsed log entry values."
    line_no = 0
    #locale = getlocale() # (LC_ALL)
    #if sys.platform == 'win32':
        #setlocale(LC_ALL, 'English_United States')
    #else:
        #setlocale(LC_ALL, 'en_US')
    try:
        clean = (line.strip() for line in lines)
        entry_lines = []
        timestamp = None
        source_id = 'UNKNOWN'
        for line in clean:
            line_no += 1
            if line == '':
                continue
            items = line.split()
            if len(items) > 5:  # It's potentially new entry
                try:
                    new_timestamp = datetime.strptime(' '.join(items[len(items)-5:]),
                                                      '%a %b %d %H:%M:%S %Y')
                except ValueError:
                    new_timestamp = None
                if new_timestamp is not None:
                    if entry_lines:
                        yield (source_id, timestamp, '\n'.join(entry_lines))
                        entry_lines = []
                    # Init new entry
                    timestamp = new_timestamp
                    source_id = ' '.join(items[:len(items)-5])
                else:
                    entry_lines.append(line)
            else:
                entry_lines.append(line)
        if entry_lines:
            yield (source_id, timestamp, '\n'.join(entry_lines))
    except Exception as exc:
        raise ParseError("Can't parse line %d\n%s" % (line_no, exc.message))
    #finally:
        #if locale[0] is None:
            #if sys.platform == 'win32':
                #setlocale(LC_ALL, '')
            #else:
                #resetlocale(LC_ALL)
        #else:
            #setlocale(LC_ALL, locale)

def monitor_log():
    """Thread target code to monitor the Firebird log."""

def process_log(context: zmq.Context, identity: bytes,
                source: pb.LogSource, target_address: ZMQAddress,
                can_send, stop):
    """Thread target code to process the Firebird log."""

    def lines_from_file(filename):
        with open(filename, 'r') as logfile:
            for line in logfile:
                yield line

    def send_fuse(seconds=1):
        while not stop.is_set() and socket.poll(seconds * 1000, zmq.POLLOUT) == 0:
            log.debug("poll(POLLOUT) TIMEOUT")
        if stop.is_set():
            return True
        while not stop.is_set() and can_send.wait(seconds) != True:
            log.debug('can_send.wait() TIMEOUT')
        return stop.is_set()

    #
    log.debug("process_log(%s, %s)", source, target_address)
    entry = pb.FirebirdLogEntry()
    socket = context.socket(zmq.DEALER)
    socket.IDENTITY = identity
    socket.LINGER = 10000 # 10s
    socket.SNDHWM = 50
    socket.connect(target_address)
    try:
        if source.WhichOneof('source') == 'filespec':
            log_gen = lines_from_file(source.filespec)
        elif source.WhichOneof('source') == 'server':
            pass
        else: # Pipe
            pass
        try:
            entry_in = 0
            entry_out = 0
            for source_id, timestamp, message in parse_log(log_gen):
                if send_fuse():
                    break
                entry.Clear()
                entry.source_id = source_id
                entry.timestamp.FromDatetime(timestamp)
                entry.message = message
                entry_in += 1
                socket.send(entry.SerializeToString())
                entry_out += 1
        except ParseError as exc:
            entry.Clear()
            entry.source_id = 'ERROR/firebird-log'
            entry.timestamp.GetCurrentTime()
            entry.message = str(exc)
            log.debug("sending 'ERROR/firebird-log' message")
            socket.send(entry.SerializeToString())
            raise
        else:
            if stop.is_set():
                if can_send.is_set() and socket.poll(10, zmq.POLLOUT) != 0:
                    log.debug("sending TERMINATED message")
                    socket.send(TERMINATED)
            else:
                if not send_fuse():
                    log.debug("sending EOF message")
                    socket.send(EOF)
    finally:
        log.debug("closing socket, going home")
        socket.close()

# Classes

class Worker:
    """Worker thread.

Attributes:
    :mode:       Worker execution mode.
    :runtime:    None, or threading.Thread or multiprocessing.Process instance.
"""
    def __init__(self, session: TSession, request: TMessage, task: Callable,
                 args: List = (), kwargs=None, mode: ExecutionMode = ExecutionMode.ANY):
        self.session = session
        self.request = request
        self.task = task
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        if mode != ExecutionMode.ANY:
            self.mode = mode
        else:
            self.mode = ExecutionMode.THREAD
        self.can_send_event: threading.Event = None
        self.stop_event: threading.Event = None
        self.runtime = None
        self.deffered_msg = None
    def disable(self) -> None:
        """Disable worker so it does not send messages."""
        log.debug("%s.disable", self.__class__.__name__)
        if self.can_send_event:
            self.can_send_event.clear()
    def enable(self) -> None:
        """Enable worker so it can send messages."""
        log.debug("%s.enable", self.__class__.__name__)
        if self.can_send_event:
            self.can_send_event.set()
    def is_enabled(self) -> None:
        """Return True if worker can send messages."""
        return self.can_send_event.is_set() if self.can_send_event else False
    def is_running(self) -> bool:
        """Returns True if service is running."""
        if self.runtime is None:
            return False
        if self.runtime.is_alive():
            return True
        # It's dead, so dispose the runtime
        self.runtime = None
        return False
    def start(self):
        """Start the worker.

If `mode` is ANY or THREAD, the worker is executed in it's own thread. Otherwise it is
executed in separate child process.
"""
        log.info("%s.start", self.__class__.__name__)
        if self.is_running():
            raise ServiceError("The worker is already running")
        args = self.args.copy()
        if self.mode in (ExecutionMode.ANY, ExecutionMode.THREAD):
            self.can_send_event = threading.Event()
            args.append(self.can_send_event)
            self.stop_event = threading.Event()
            args.append(self.stop_event)
            self.runtime = threading.Thread(target=self.task, args=args, kwargs=self.kwargs)
        else:
            self.can_send_event = multiprocessing.Event()
            args.append(self.can_send_event)
            self.stop_event = multiprocessing.Event()
            args.append(self.stop_event)
            self.runtime = multiprocessing.Process(target=self.task, args=args,
                                                   kwargs=self.kwargs)
        self.runtime.start()
    def stop(self, timeout=None):
        """Stop the worker. Does nothing if worker is not running.

Arguments:
    :timeout: None (infinity), or a floating point number specifying a timeout for
              the operation in seconds (or fractions thereof) [Default: None].

Raises:
    :TimeoutError:  The service did not stop on time.
"""
        log.info("%s.stop", self.__class__.__name__)
        if self.is_running():
            self.stop_event.set()
            self.runtime.join(timeout=timeout)
            if self.runtime.is_alive():
                raise TimeoutError("The worker did not stop on time")
            self.runtime = None
        log.info("Worker stopped")
    def terminate(self):
        """Terminate the service.

Terminate should be called ONLY when call to stop() (with sensible timeout) fails.
Does nothing when service is not running.

Raises:
    :ServiceError:  When service termination fails.
"""
        log.info("%s.terminate", self.__class__.__name__)
        if self.is_running():
            tid = ctypes.c_long(self.runtime.ident)
            if isinstance(self.runtime, threading.Thread):
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(SystemExit))
                if res == 0:
                    raise ServiceError("Service termination failed due to invalid thread ID.")
                if res != 1:
                    # if it returns a number greater than one, you're in trouble,
                    # and you should call it again with exc=NULL to revert the effect
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
                    raise ServiceError("Service termination failed due to PyThreadState_SetAsyncExc failure")
            elif isinstance(self.runtime, multiprocessing.Process):
                self.runtime.terminate()
            else:
                raise ServiceError("Service termination failed - invalid runtime.")

class FirebirdLogMessageHandler(ServiceMessagelHandler):
    """Message handler for Firebird log service."""
    def __init__(self, chn: TChannel, service: TServiceImpl):
        super().__init__(chn, service)
        # Our message handlers
        self.handlers.update({(MsgType.REQUEST, bb2h(1, FbLogRequest.MONITOR)):
                              self.on_monitor,
                              (MsgType.REQUEST, bb2h(1, FbLogRequest.STOP_MONITOR)):
                              self.on_stop_monitor,
                              (MsgType.REQUEST, bb2h(1, FbLogRequest.ENTRIES)):
                              self.on_entries,
                              MsgType.DATA: self.send_protocol_violation,
                              })
    def suspend_session(self, session: TSession) -> None:
        """Called by send() when message must be deferred for later delivery.

Disables the worker to do not send further messages.
"""
        worker = self.impl.get_worker(session)
        if worker:
            worker.disable()
    def resume_session(self, session: TSession) -> None:
        """Called by __resend() when deferred message is sent successfully.

Enables the worker to send further messages.
"""
        worker = self.impl.get_worker(session)
        if worker:
            worker.enable()
    def cancel_session(self, session: TSession) -> None:
        """Called by __resend() when attempts to send the message keep failing over specified
time threashold.

Stops the worker and discards the session."""
        worker = self.impl.get_worker(session)
        self.impl.drop_worker(worker)
        self.discard_session(session)
    def on_ack_reply(self, session: TSession, msg: TMessage) -> None:
        """Called by `on_reply()` to handle REPLY/ACK_REPLY message.

When acknowledged message is REPLY/ENTRIES, lets worker to start sending messages.
"""
        log.info("%s.on_ack_reply", self.__class__.__name__)
        if ((msg.message_type == MsgType.REPLY) and
                (msg.type_data == bb2h(1, FbLogRequest.ENTRIES))):
            self.impl.get_worker(session).enable()
    def on_hello(self, session: TSession, msg: HelloMessage):
        "HELLO message handler. Sends WELCOME message back to the client."
        log.info("%s.on_hello(%s)", self.__class__.__name__, session.routing_id)
        super().on_hello(session, msg)
        welcome = self.protocol.create_welcome_reply(msg)
        welcome.peer.CopyFrom(self.impl.welcome_df)
        self.send(welcome, session)
    def on_cancel(self, session: TSession, msg: CancelMessage):
        "Handle CANCEL message."
        # We support CANCEL for ENTRIES requests
        log.info("%s.on_cancel(%s)", self.__class__.__name__, session.routing_id)
    def on_monitor(self, session: TSession, msg: RequestMessage):
        "Handle REQUEST/MONITOR message."
        log.debug("%s.on_monitor(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        #dframe = pb.ReplyInstalledServices()
        #reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def on_stop_monitor(self, session: TSession, msg: RequestMessage):
        "Handle REQUEST/STOP_MONITOR message."
        log.debug("%s.on_stop_monitor(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        #dframe = pb.ReplyInstalledServices()
        #reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def on_entries(self, session: TSession, msg: RequestMessage):
        "Handle REQUEST/ENTRIES message."
        log.debug("%s.on_entries(%s)", self.__class__.__name__, session.routing_id)
        address = self.impl.worker_chn.endpoints[0]
        dframe = pb.RequestEntries()
        dframe.ParseFromString(msg.data[0])
        # validate request
        if dframe.HasField('push_to'):
            if dframe.push_to.protocol != "pb-stream:fblog:FirebirdLogEntry":
                errmsg = self.create_error_message(msg, "Data pipe protocol not supported")
                self.send(errmsg, session)
                return
            if SocketType(dframe.push_to.socket_type) not in [SocketType.DEALER,
                                                              SocketType.PULL,
                                                              SocketType.ROUTER]:
                errmsg = self.create_error_message(msg, "Data pipe uses unsupported socket type")
                self.send(errmsg, session)
                return
            if SocketUse(dframe.push_to.use) != SocketUse.CONSUMER:
                errmsg = self.create_error_message(msg, "CONSUMER data pipe required")
                self.send(errmsg, session)
                return
            address = get_best_endpoint([toZMQAddress(e) for e in dframe.push_to.endpoints],
                                        self.impl.peer.host, self.impl.peer.pid,
                                        dframe.push_to.host, dframe.push_to.pid)
            if address is None:
                errmsg = self.create_error_message(msg, "No accessible data pipe address found")
                self.send(errmsg, session)
                return
        if dframe.source.WhichOneof('source') == 'server':
            errmsg = self.create_error_message(msg, "Source 'server' not supported")
            self.send(errmsg, session)
            return
        if dframe.source.WhichOneof('source') == 'pipe':
            errmsg = self.create_error_message(msg, "Source 'pipe' not supported")
            self.send(errmsg, session)
            return
        #
        try:
            log.debug("%s.on_entries(%s) worker sends to '%s'",
                      self.__class__.__name__, session.routing_id, address)
            worker = self.impl.add_worker(session, msg, process_log, dframe.source, address)
            worker.start()
        except ServiceError as exc: # Expected error condition
            errmsg = self.protocol.create_error_for(msg, ErrorCode.ERROR)
            note_exception(errmsg, exc)
            self.send(errmsg, session)
        except Exception as exc: # Unexpected error condition
            errmsg = self.protocol.create_error_for(msg, ErrorCode.INTERNAL_SERVICE_ERROR)
            note_exception(errmsg, exc)
            self.send(errmsg, session)
        else:
            # Send reply
            reply = self.protocol.create_reply_for(msg)
            reply.set_flag(MsgFlag.ACK_REQ)
            self.send(reply, session)

class WorkerMessageHandler(BaseMessageHandler):
    """Message handler for workers."""
    def __init__(self, chn: TChannel, service_impl: TServiceImpl):
        super().__init__(chn, Origin.CONSUMER)
        self.impl: TServiceImpl = service_impl
        self.fbsp = service_impl.msg_handler.protocol
    def dispatch(self, session: TSession, msg: TMessage) -> None:
        """Process message received from worker.

Arguments:
    :session: Session instance.
    :msg:     Received message.
"""
        worker = self.impl.get_worker(session)
        if worker:
            if msg.data[0] == EOF:
                data_msg = self.fbsp.create_state_for(worker.request, State.FINISHED)
                self.impl.drop_worker(worker)
            elif msg.data[0] == TERMINATED:
                data_msg = self.fbsp.create_state_for(worker.request, State.TERMINATED)
                self.impl.drop_worker(worker)
            else:
                data_msg = self.fbsp.create_data_for(worker.request)
                data_msg.data.extend(msg.data)
            self.impl.msg_handler.send(data_msg, worker.session)
        else:
            log.info("Ignoring message from dead worker")

class FirebirdLogServiceImpl(SimpleServiceImpl):
    """Implementation of Firebird Log service."""
    def __init__(self, stop_event: Any):
        super().__init__(stop_event)
        self.agent = SERVICE_AGENT
        self.api = SERVICE_API
        self.workers: Dict[UUID, Worker] = {}
        self.worker_chn = None
        self.worker_handler = None
    def get_sock_opts(self) -> Dict[str, Any]:
        "Return socket options for main service (router) channel."
        return {'sndhwm': 100, 'rcvhwm': 30, }
    def initialize(self, svc: BaseService):
        super().initialize(svc)
        self.msg_handler = FirebirdLogMessageHandler(self.svc_chn, self)
        self.worker_chn = RouterChannel(self.instance_id,
                                        sock_opts={'sndhwm': 10, 'rcvhwm': 30})
        self.worker_handler = WorkerMessageHandler(self.worker_chn, self)
        self.mngr.add(self.worker_chn)
        self.worker_chn.bind(ZMQAddress('inproc://%s:workers' % self.peer.uid))
    def finalize(self, svc: TService) -> None:
        """Service finalization. Stops/terminates all running workers.
"""
        log.debug("%s.finalize", self.__class__.__name__)
        # Stop running requests
        for worker in self.workers.values():
            try:
                worker.stop()
            except:
                try:
                    log.info("Worker %s did not stop on time, terminating...", worker.name)
                    worker.terminate()
                except:
                    log.warning("Could't stop worker %s", worker.name)
        super().finalize(svc)
    def add_worker(self, session: TSession, request: TMessage, task: Callable,
                   source: pb.LogSource, address: ZMQAddress) -> Worker:
        """Returns newly created worker."""
        log.info("%s.add_worker", self.__class__.__name__)
        worker = Worker(session, request, task, args=[self.mngr.ctx, session.routing_id,
                                                      source, address])
        self.workers[session.routing_id] = worker
        return worker
    def drop_worker(self, worker: Worker) -> None:
        "Stops and then drops the worker"
        log.info("%s.drop_worker", self.__class__.__name__)
        try:
            worker.stop(5)
        except TimeoutError:
            worker.terminate()
        del self.workers[worker.session.routing_id]
    def get_worker(self, session) -> Worker:
        """Returns worker associated session or None."""
        return self.workers.get(session.routing_id)
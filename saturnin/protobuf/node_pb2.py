# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: node.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from saturnin.protobuf import saturnin_pb2 as saturnin_dot_protobuf_dot_saturnin__pb2
try:
  saturnin_dot_sdk_dot_fbsp__pb2 = saturnin_dot_protobuf_dot_saturnin__pb2.saturnin_dot_sdk_dot_fbsp__pb2
except AttributeError:
  saturnin_dot_sdk_dot_fbsp__pb2 = saturnin_dot_protobuf_dot_saturnin__pb2.saturnin.sdk.fbsp_pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='node.proto',
  package='saturnin.node',
  syntax='proto3',
  serialized_pb=_b('\n\nnode.proto\x12\rsaturnin.node\x1a saturnin/protobuf/saturnin.proto\"F\n\x16ReplyInstalledServices\x12,\n\x08services\x18\x01 \x03(\x0b\x32\x1a.saturnin.InstalledService\"\x9d\x01\n\x0eRunningService\x12&\n\x04peer\x18\x01 \x01(\x0b\x32\x18.fbsp.PeerIdentification\x12(\n\x05\x61gent\x18\x02 \x01(\x0b\x32\x19.fbsp.AgentIdentification\x12&\n\x04mode\x18\x03 \x01(\x0e\x32\x18.saturnin.node.StartMode\x12\x11\n\tendpoints\x18\x04 \x03(\t\"G\n\x14ReplyRunningServices\x12/\n\x08services\x18\x01 \x03(\x0b\x32\x1d.saturnin.node.RunningService\"2\n\x19RequestInterfaceProviders\x12\x15\n\rinterface_uid\x18\x01 \x01(\x0c\"-\n\x17ReplyInterfaceProviders\x12\x12\n\nagent_uids\x18\x01 \x03(\x0c\"\x8b\x01\n\x13RequestStartService\x12\x11\n\tagent_uid\x18\x01 \x01(\x0c\x12&\n\x04mode\x18\x02 \x01(\x0e\x32\x18.saturnin.node.StartMode\x12\x11\n\tendpoints\x18\x03 \x03(\t\x12\x0f\n\x07timeout\x18\x04 \x01(\r\x12\x15\n\rmultiinstance\x18\x05 \x01(\x08\"`\n\x11ReplyStartService\x12\x10\n\x08peer_uid\x18\x01 \x01(\x0c\x12&\n\x04mode\x18\x02 \x01(\x0e\x32\x18.saturnin.node.StartMode\x12\x11\n\tendpoints\x18\x03 \x03(\t\"G\n\x12RequestStopService\x12\x10\n\x08peer_uid\x18\x01 \x01(\x0c\x12\x0f\n\x07timeout\x18\x02 \x01(\r\x12\x0e\n\x06\x66orced\x18\x03 \x01(\x08\"/\n\x10ReplyStopService\x12\x1b\n\x06result\x18\x01 \x01(\x0e\x32\x0b.fbsp.State\"=\n\x12RequestGetProvider\x12\x15\n\rinterface_uid\x18\x01 \x01(\x0c\x12\x10\n\x08required\x18\x02 \x01(\x08\"$\n\x10ReplyGetProvider\x12\x10\n\x08\x65ndpoint\x18\x01 \x01(\t*1\n\tStartMode\x12\x0b\n\x07\x44\x45\x46\x41ULT\x10\x00\x12\n\n\x06THREAD\x10\x01\x12\x0b\n\x07PROCESS\x10\x02\x62\x06proto3')
  ,
  dependencies=[saturnin_dot_protobuf_dot_saturnin__pb2.DESCRIPTOR,])

_STARTMODE = _descriptor.EnumDescriptor(
  name='StartMode',
  full_name='saturnin.node.StartMode',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='DEFAULT', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='THREAD', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PROCESS', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=930,
  serialized_end=979,
)
_sym_db.RegisterEnumDescriptor(_STARTMODE)

StartMode = enum_type_wrapper.EnumTypeWrapper(_STARTMODE)
DEFAULT = 0
THREAD = 1
PROCESS = 2



_REPLYINSTALLEDSERVICES = _descriptor.Descriptor(
  name='ReplyInstalledServices',
  full_name='saturnin.node.ReplyInstalledServices',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='services', full_name='saturnin.node.ReplyInstalledServices.services', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=63,
  serialized_end=133,
)


_RUNNINGSERVICE = _descriptor.Descriptor(
  name='RunningService',
  full_name='saturnin.node.RunningService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='peer', full_name='saturnin.node.RunningService.peer', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='agent', full_name='saturnin.node.RunningService.agent', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mode', full_name='saturnin.node.RunningService.mode', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='endpoints', full_name='saturnin.node.RunningService.endpoints', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=136,
  serialized_end=293,
)


_REPLYRUNNINGSERVICES = _descriptor.Descriptor(
  name='ReplyRunningServices',
  full_name='saturnin.node.ReplyRunningServices',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='services', full_name='saturnin.node.ReplyRunningServices.services', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=295,
  serialized_end=366,
)


_REQUESTINTERFACEPROVIDERS = _descriptor.Descriptor(
  name='RequestInterfaceProviders',
  full_name='saturnin.node.RequestInterfaceProviders',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='interface_uid', full_name='saturnin.node.RequestInterfaceProviders.interface_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=368,
  serialized_end=418,
)


_REPLYINTERFACEPROVIDERS = _descriptor.Descriptor(
  name='ReplyInterfaceProviders',
  full_name='saturnin.node.ReplyInterfaceProviders',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uids', full_name='saturnin.node.ReplyInterfaceProviders.agent_uids', index=0,
      number=1, type=12, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=420,
  serialized_end=465,
)


_REQUESTSTARTSERVICE = _descriptor.Descriptor(
  name='RequestStartService',
  full_name='saturnin.node.RequestStartService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uid', full_name='saturnin.node.RequestStartService.agent_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mode', full_name='saturnin.node.RequestStartService.mode', index=1,
      number=2, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='endpoints', full_name='saturnin.node.RequestStartService.endpoints', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='saturnin.node.RequestStartService.timeout', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='multiinstance', full_name='saturnin.node.RequestStartService.multiinstance', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=468,
  serialized_end=607,
)


_REPLYSTARTSERVICE = _descriptor.Descriptor(
  name='ReplyStartService',
  full_name='saturnin.node.ReplyStartService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='peer_uid', full_name='saturnin.node.ReplyStartService.peer_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mode', full_name='saturnin.node.ReplyStartService.mode', index=1,
      number=2, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='endpoints', full_name='saturnin.node.ReplyStartService.endpoints', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=609,
  serialized_end=705,
)


_REQUESTSTOPSERVICE = _descriptor.Descriptor(
  name='RequestStopService',
  full_name='saturnin.node.RequestStopService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='peer_uid', full_name='saturnin.node.RequestStopService.peer_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='saturnin.node.RequestStopService.timeout', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='forced', full_name='saturnin.node.RequestStopService.forced', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=707,
  serialized_end=778,
)


_REPLYSTOPSERVICE = _descriptor.Descriptor(
  name='ReplyStopService',
  full_name='saturnin.node.ReplyStopService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='result', full_name='saturnin.node.ReplyStopService.result', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=780,
  serialized_end=827,
)


_REQUESTGETPROVIDER = _descriptor.Descriptor(
  name='RequestGetProvider',
  full_name='saturnin.node.RequestGetProvider',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='interface_uid', full_name='saturnin.node.RequestGetProvider.interface_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='required', full_name='saturnin.node.RequestGetProvider.required', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=829,
  serialized_end=890,
)


_REPLYGETPROVIDER = _descriptor.Descriptor(
  name='ReplyGetProvider',
  full_name='saturnin.node.ReplyGetProvider',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='endpoint', full_name='saturnin.node.ReplyGetProvider.endpoint', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=892,
  serialized_end=928,
)

_REPLYINSTALLEDSERVICES.fields_by_name['services'].message_type = saturnin_dot_protobuf_dot_saturnin__pb2._INSTALLEDSERVICE
_RUNNINGSERVICE.fields_by_name['peer'].message_type = saturnin_dot_sdk_dot_fbsp__pb2._PEERIDENTIFICATION
_RUNNINGSERVICE.fields_by_name['agent'].message_type = saturnin_dot_sdk_dot_fbsp__pb2._AGENTIDENTIFICATION
_RUNNINGSERVICE.fields_by_name['mode'].enum_type = _STARTMODE
_REPLYRUNNINGSERVICES.fields_by_name['services'].message_type = _RUNNINGSERVICE
_REQUESTSTARTSERVICE.fields_by_name['mode'].enum_type = _STARTMODE
_REPLYSTARTSERVICE.fields_by_name['mode'].enum_type = _STARTMODE
_REPLYSTOPSERVICE.fields_by_name['result'].enum_type = saturnin_dot_sdk_dot_fbsp__pb2._STATE
DESCRIPTOR.message_types_by_name['ReplyInstalledServices'] = _REPLYINSTALLEDSERVICES
DESCRIPTOR.message_types_by_name['RunningService'] = _RUNNINGSERVICE
DESCRIPTOR.message_types_by_name['ReplyRunningServices'] = _REPLYRUNNINGSERVICES
DESCRIPTOR.message_types_by_name['RequestInterfaceProviders'] = _REQUESTINTERFACEPROVIDERS
DESCRIPTOR.message_types_by_name['ReplyInterfaceProviders'] = _REPLYINTERFACEPROVIDERS
DESCRIPTOR.message_types_by_name['RequestStartService'] = _REQUESTSTARTSERVICE
DESCRIPTOR.message_types_by_name['ReplyStartService'] = _REPLYSTARTSERVICE
DESCRIPTOR.message_types_by_name['RequestStopService'] = _REQUESTSTOPSERVICE
DESCRIPTOR.message_types_by_name['ReplyStopService'] = _REPLYSTOPSERVICE
DESCRIPTOR.message_types_by_name['RequestGetProvider'] = _REQUESTGETPROVIDER
DESCRIPTOR.message_types_by_name['ReplyGetProvider'] = _REPLYGETPROVIDER
DESCRIPTOR.enum_types_by_name['StartMode'] = _STARTMODE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

ReplyInstalledServices = _reflection.GeneratedProtocolMessageType('ReplyInstalledServices', (_message.Message,), dict(
  DESCRIPTOR = _REPLYINSTALLEDSERVICES,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyInstalledServices)
  ))
_sym_db.RegisterMessage(ReplyInstalledServices)

RunningService = _reflection.GeneratedProtocolMessageType('RunningService', (_message.Message,), dict(
  DESCRIPTOR = _RUNNINGSERVICE,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.RunningService)
  ))
_sym_db.RegisterMessage(RunningService)

ReplyRunningServices = _reflection.GeneratedProtocolMessageType('ReplyRunningServices', (_message.Message,), dict(
  DESCRIPTOR = _REPLYRUNNINGSERVICES,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyRunningServices)
  ))
_sym_db.RegisterMessage(ReplyRunningServices)

RequestInterfaceProviders = _reflection.GeneratedProtocolMessageType('RequestInterfaceProviders', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTINTERFACEPROVIDERS,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.RequestInterfaceProviders)
  ))
_sym_db.RegisterMessage(RequestInterfaceProviders)

ReplyInterfaceProviders = _reflection.GeneratedProtocolMessageType('ReplyInterfaceProviders', (_message.Message,), dict(
  DESCRIPTOR = _REPLYINTERFACEPROVIDERS,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyInterfaceProviders)
  ))
_sym_db.RegisterMessage(ReplyInterfaceProviders)

RequestStartService = _reflection.GeneratedProtocolMessageType('RequestStartService', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSTARTSERVICE,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.RequestStartService)
  ))
_sym_db.RegisterMessage(RequestStartService)

ReplyStartService = _reflection.GeneratedProtocolMessageType('ReplyStartService', (_message.Message,), dict(
  DESCRIPTOR = _REPLYSTARTSERVICE,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyStartService)
  ))
_sym_db.RegisterMessage(ReplyStartService)

RequestStopService = _reflection.GeneratedProtocolMessageType('RequestStopService', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSTOPSERVICE,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.RequestStopService)
  ))
_sym_db.RegisterMessage(RequestStopService)

ReplyStopService = _reflection.GeneratedProtocolMessageType('ReplyStopService', (_message.Message,), dict(
  DESCRIPTOR = _REPLYSTOPSERVICE,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyStopService)
  ))
_sym_db.RegisterMessage(ReplyStopService)

RequestGetProvider = _reflection.GeneratedProtocolMessageType('RequestGetProvider', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTGETPROVIDER,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.RequestGetProvider)
  ))
_sym_db.RegisterMessage(RequestGetProvider)

ReplyGetProvider = _reflection.GeneratedProtocolMessageType('ReplyGetProvider', (_message.Message,), dict(
  DESCRIPTOR = _REPLYGETPROVIDER,
  __module__ = 'node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.node.ReplyGetProvider)
  ))
_sym_db.RegisterMessage(ReplyGetProvider)


# @@protoc_insertion_point(module_scope)

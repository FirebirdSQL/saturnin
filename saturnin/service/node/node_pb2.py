# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: saturnin/service/node/node.proto

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


from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
from google.protobuf import struct_pb2 as google_dot_protobuf_dot_struct__pb2
from firebird.butler import fbsd_pb2 as firebird_dot_butler_dot_fbsd__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='saturnin/service/node/node.proto',
  package='saturnin.protobuf',
  syntax='proto3',
  serialized_pb=_b('\n saturnin/service/node/node.proto\x12\x11saturnin.protobuf\x1a\x19google/protobuf/any.proto\x1a\x1cgoogle/protobuf/struct.proto\x1a\x1a\x66irebird/butler/fbsd.proto\"L\n\nDependency\x12\x31\n\x04type\x18\x01 \x01(\x0e\x32#.firebird.butler.DependencyTypeEnum\x12\x0b\n\x03uid\x18\x02 \x01(\x0c\")\n\x0bRequestCode\x12\x0c\n\x04\x63ode\x18\x01 \x01(\r\x12\x0c\n\x04name\x18\x02 \x01(\t\"\x84\x01\n\x13InterfaceDescriptor\x12\x0b\n\x03uid\x18\x01 \x01(\x0c\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x10\n\x08revision\x18\x03 \x01(\r\x12\x0e\n\x06number\x18\x04 \x01(\r\x12\x30\n\x08requests\x18\x05 \x03(\x0b\x32\x1e.saturnin.protobuf.RequestCode\"\x9c\x03\n\x10InstalledService\x12\x33\n\x05\x61gent\x18\x01 \x01(\x0b\x32$.firebird.butler.AgentIdentification\x12\x33\n\x03\x61pi\x18\x02 \x03(\x0b\x32&.saturnin.protobuf.InterfaceDescriptor\x12\x33\n\x0c\x64\x65pendencies\x18\x03 \x03(\x0b\x32\x1d.saturnin.protobuf.Dependency\x12\x38\n\x0cservice_type\x18\x04 \x01(\x0e\x32\".saturnin.protobuf.ServiceTypeEnum\x12\x13\n\x0b\x64\x65scription\x18\x05 \x01(\t\x12\x32\n\x04mode\x18\x06 \x01(\x0e\x32$.saturnin.protobuf.ExecutionModeEnum\x12<\n\nfacilities\x18\x07 \x03(\x0e\x32(.saturnin.protobuf.ServiceFacilitiesEnum\x12(\n\nsupplement\x18\x08 \x03(\x0b\x32\x14.google.protobuf.Any\"O\n\x16ReplyInstalledServices\x12\x35\n\x08services\x18\x01 \x03(\x0b\x32#.saturnin.protobuf.InstalledService\"\x9f\x03\n\x0eRunningService\x12\x31\n\x04peer\x18\x01 \x01(\x0b\x32#.firebird.butler.PeerIdentification\x12\x33\n\x05\x61gent\x18\x02 \x01(\x0b\x32$.firebird.butler.AgentIdentification\x12\x38\n\x0cservice_type\x18\x03 \x01(\x0e\x32\".saturnin.protobuf.ServiceTypeEnum\x12\x13\n\x0b\x64\x65scription\x18\x04 \x01(\t\x12\x32\n\x04mode\x18\x05 \x01(\x0e\x32$.saturnin.protobuf.ExecutionModeEnum\x12<\n\nfacilities\x18\x06 \x03(\x0e\x32(.saturnin.protobuf.ServiceFacilitiesEnum\x12\'\n\x06\x63onfig\x18\x07 \x01(\x0b\x32\x17.google.protobuf.Struct\x12\x11\n\tendpoints\x18\x08 \x03(\t\x12(\n\nsupplement\x18\t \x03(\x0b\x32\x14.google.protobuf.Any\"K\n\x14ReplyRunningServices\x12\x33\n\x08services\x18\x01 \x03(\x0b\x32!.saturnin.protobuf.RunningService\"2\n\x19RequestInterfaceProviders\x12\x15\n\rinterface_uid\x18\x01 \x01(\x0c\"-\n\x17ReplyInterfaceProviders\x12\x12\n\nagent_uids\x18\x01 \x03(\x0c\"\x83\x01\n\x13RequestStartService\x12\x11\n\tagent_uid\x18\x01 \x01(\x0c\x12\'\n\x06\x63onfig\x18\x02 \x01(\x0b\x32\x17.google.protobuf.Struct\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x0f\n\x07timeout\x18\x04 \x01(\r\x12\x11\n\tsingleton\x18\x05 \x01(\x08\"G\n\x11ReplyStartService\x12\x32\n\x07service\x18\x01 \x01(\x0b\x32!.saturnin.protobuf.RunningService\"G\n\x12RequestStopService\x12\x10\n\x08peer_uid\x18\x01 \x01(\x0c\x12\x0f\n\x07timeout\x18\x02 \x01(\r\x12\x0e\n\x06\x66orced\x18\x03 \x01(\x08\">\n\x10ReplyStopService\x12*\n\x06result\x18\x01 \x01(\x0e\x32\x1a.firebird.butler.StateEnum*S\n\x11\x45xecutionModeEnum\x12\x11\n\rEXEC_MODE_ANY\x10\x00\x12\x14\n\x10\x45XEC_MODE_THREAD\x10\x01\x12\x15\n\x11\x45XEC_MODE_PROCESS\x10\x02*\xbf\x01\n\x0fServiceTypeEnum\x12\x14\n\x10SVC_TYPE_UNKNOWN\x10\x00\x12\x1a\n\x16SVC_TYPE_DATA_PROVIDER\x10\x01\x12\x18\n\x14SVC_TYPE_DATA_FILTER\x10\x02\x12\x1a\n\x16SVC_TYPE_DATA_CONSUMER\x10\x03\x12\x17\n\x13SVC_TYPE_PROCESSING\x10\x04\x12\x15\n\x11SVC_TYPE_EXECUTOR\x10\x05\x12\x14\n\x10SVC_TYPE_CONTROL\x10\x06*\xca\x01\n\x15ServiceFacilitiesEnum\x12\x15\n\x11SVC_FACILITY_NONE\x10\x00\x12\x1c\n\x18SVC_FACILITY_FBSP_SOCKET\x10\x01\x12\x1d\n\x19SVC_FACILITY_INPUT_SERVER\x10\x02\x12\x1d\n\x19SVC_FACILITY_INPUT_CLIENT\x10\x03\x12\x1e\n\x1aSVC_FACILITY_OUTPUT_SERVER\x10\x04\x12\x1e\n\x1aSVC_FACILITY_OUTPUT_CLIENT\x10\x05\x62\x06proto3')
  ,
  dependencies=[google_dot_protobuf_dot_any__pb2.DESCRIPTOR,google_dot_protobuf_dot_struct__pb2.DESCRIPTOR,firebird_dot_butler_dot_fbsd__pb2.DESCRIPTOR,])

_EXECUTIONMODEENUM = _descriptor.EnumDescriptor(
  name='ExecutionModeEnum',
  full_name='saturnin.protobuf.ExecutionModeEnum',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='EXEC_MODE_ANY', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='EXEC_MODE_THREAD', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='EXEC_MODE_PROCESS', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1830,
  serialized_end=1913,
)
_sym_db.RegisterEnumDescriptor(_EXECUTIONMODEENUM)

ExecutionModeEnum = enum_type_wrapper.EnumTypeWrapper(_EXECUTIONMODEENUM)
_SERVICETYPEENUM = _descriptor.EnumDescriptor(
  name='ServiceTypeEnum',
  full_name='saturnin.protobuf.ServiceTypeEnum',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_UNKNOWN', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_DATA_PROVIDER', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_DATA_FILTER', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_DATA_CONSUMER', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_PROCESSING', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_EXECUTOR', index=5, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_TYPE_CONTROL', index=6, number=6,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1916,
  serialized_end=2107,
)
_sym_db.RegisterEnumDescriptor(_SERVICETYPEENUM)

ServiceTypeEnum = enum_type_wrapper.EnumTypeWrapper(_SERVICETYPEENUM)
_SERVICEFACILITIESENUM = _descriptor.EnumDescriptor(
  name='ServiceFacilitiesEnum',
  full_name='saturnin.protobuf.ServiceFacilitiesEnum',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_NONE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_FBSP_SOCKET', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_INPUT_SERVER', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_INPUT_CLIENT', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_OUTPUT_SERVER', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SVC_FACILITY_OUTPUT_CLIENT', index=5, number=5,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=2110,
  serialized_end=2312,
)
_sym_db.RegisterEnumDescriptor(_SERVICEFACILITIESENUM)

ServiceFacilitiesEnum = enum_type_wrapper.EnumTypeWrapper(_SERVICEFACILITIESENUM)
EXEC_MODE_ANY = 0
EXEC_MODE_THREAD = 1
EXEC_MODE_PROCESS = 2
SVC_TYPE_UNKNOWN = 0
SVC_TYPE_DATA_PROVIDER = 1
SVC_TYPE_DATA_FILTER = 2
SVC_TYPE_DATA_CONSUMER = 3
SVC_TYPE_PROCESSING = 4
SVC_TYPE_EXECUTOR = 5
SVC_TYPE_CONTROL = 6
SVC_FACILITY_NONE = 0
SVC_FACILITY_FBSP_SOCKET = 1
SVC_FACILITY_INPUT_SERVER = 2
SVC_FACILITY_INPUT_CLIENT = 3
SVC_FACILITY_OUTPUT_SERVER = 4
SVC_FACILITY_OUTPUT_CLIENT = 5



_DEPENDENCY = _descriptor.Descriptor(
  name='Dependency',
  full_name='saturnin.protobuf.Dependency',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='type', full_name='saturnin.protobuf.Dependency.type', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='uid', full_name='saturnin.protobuf.Dependency.uid', index=1,
      number=2, type=12, cpp_type=9, label=1,
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
  serialized_start=140,
  serialized_end=216,
)


_REQUESTCODE = _descriptor.Descriptor(
  name='RequestCode',
  full_name='saturnin.protobuf.RequestCode',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='code', full_name='saturnin.protobuf.RequestCode.code', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='saturnin.protobuf.RequestCode.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
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
  serialized_start=218,
  serialized_end=259,
)


_INTERFACEDESCRIPTOR = _descriptor.Descriptor(
  name='InterfaceDescriptor',
  full_name='saturnin.protobuf.InterfaceDescriptor',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='uid', full_name='saturnin.protobuf.InterfaceDescriptor.uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='saturnin.protobuf.InterfaceDescriptor.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='revision', full_name='saturnin.protobuf.InterfaceDescriptor.revision', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='number', full_name='saturnin.protobuf.InterfaceDescriptor.number', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='requests', full_name='saturnin.protobuf.InterfaceDescriptor.requests', index=4,
      number=5, type=11, cpp_type=10, label=3,
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
  serialized_start=262,
  serialized_end=394,
)


_INSTALLEDSERVICE = _descriptor.Descriptor(
  name='InstalledService',
  full_name='saturnin.protobuf.InstalledService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent', full_name='saturnin.protobuf.InstalledService.agent', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='api', full_name='saturnin.protobuf.InstalledService.api', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='dependencies', full_name='saturnin.protobuf.InstalledService.dependencies', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='service_type', full_name='saturnin.protobuf.InstalledService.service_type', index=3,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='description', full_name='saturnin.protobuf.InstalledService.description', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mode', full_name='saturnin.protobuf.InstalledService.mode', index=5,
      number=6, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='facilities', full_name='saturnin.protobuf.InstalledService.facilities', index=6,
      number=7, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='supplement', full_name='saturnin.protobuf.InstalledService.supplement', index=7,
      number=8, type=11, cpp_type=10, label=3,
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
  serialized_start=397,
  serialized_end=809,
)


_REPLYINSTALLEDSERVICES = _descriptor.Descriptor(
  name='ReplyInstalledServices',
  full_name='saturnin.protobuf.ReplyInstalledServices',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='services', full_name='saturnin.protobuf.ReplyInstalledServices.services', index=0,
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
  serialized_start=811,
  serialized_end=890,
)


_RUNNINGSERVICE = _descriptor.Descriptor(
  name='RunningService',
  full_name='saturnin.protobuf.RunningService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='peer', full_name='saturnin.protobuf.RunningService.peer', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='agent', full_name='saturnin.protobuf.RunningService.agent', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='service_type', full_name='saturnin.protobuf.RunningService.service_type', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='description', full_name='saturnin.protobuf.RunningService.description', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mode', full_name='saturnin.protobuf.RunningService.mode', index=4,
      number=5, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='facilities', full_name='saturnin.protobuf.RunningService.facilities', index=5,
      number=6, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='config', full_name='saturnin.protobuf.RunningService.config', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='endpoints', full_name='saturnin.protobuf.RunningService.endpoints', index=7,
      number=8, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='supplement', full_name='saturnin.protobuf.RunningService.supplement', index=8,
      number=9, type=11, cpp_type=10, label=3,
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
  serialized_start=893,
  serialized_end=1308,
)


_REPLYRUNNINGSERVICES = _descriptor.Descriptor(
  name='ReplyRunningServices',
  full_name='saturnin.protobuf.ReplyRunningServices',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='services', full_name='saturnin.protobuf.ReplyRunningServices.services', index=0,
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
  serialized_start=1310,
  serialized_end=1385,
)


_REQUESTINTERFACEPROVIDERS = _descriptor.Descriptor(
  name='RequestInterfaceProviders',
  full_name='saturnin.protobuf.RequestInterfaceProviders',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='interface_uid', full_name='saturnin.protobuf.RequestInterfaceProviders.interface_uid', index=0,
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
  serialized_start=1387,
  serialized_end=1437,
)


_REPLYINTERFACEPROVIDERS = _descriptor.Descriptor(
  name='ReplyInterfaceProviders',
  full_name='saturnin.protobuf.ReplyInterfaceProviders',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uids', full_name='saturnin.protobuf.ReplyInterfaceProviders.agent_uids', index=0,
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
  serialized_start=1439,
  serialized_end=1484,
)


_REQUESTSTARTSERVICE = _descriptor.Descriptor(
  name='RequestStartService',
  full_name='saturnin.protobuf.RequestStartService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uid', full_name='saturnin.protobuf.RequestStartService.agent_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='config', full_name='saturnin.protobuf.RequestStartService.config', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='saturnin.protobuf.RequestStartService.name', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='saturnin.protobuf.RequestStartService.timeout', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='singleton', full_name='saturnin.protobuf.RequestStartService.singleton', index=4,
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
  serialized_start=1487,
  serialized_end=1618,
)


_REPLYSTARTSERVICE = _descriptor.Descriptor(
  name='ReplyStartService',
  full_name='saturnin.protobuf.ReplyStartService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='service', full_name='saturnin.protobuf.ReplyStartService.service', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
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
  serialized_start=1620,
  serialized_end=1691,
)


_REQUESTSTOPSERVICE = _descriptor.Descriptor(
  name='RequestStopService',
  full_name='saturnin.protobuf.RequestStopService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='peer_uid', full_name='saturnin.protobuf.RequestStopService.peer_uid', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='saturnin.protobuf.RequestStopService.timeout', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='forced', full_name='saturnin.protobuf.RequestStopService.forced', index=2,
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
  serialized_start=1693,
  serialized_end=1764,
)


_REPLYSTOPSERVICE = _descriptor.Descriptor(
  name='ReplyStopService',
  full_name='saturnin.protobuf.ReplyStopService',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='result', full_name='saturnin.protobuf.ReplyStopService.result', index=0,
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
  serialized_start=1766,
  serialized_end=1828,
)

_DEPENDENCY.fields_by_name['type'].enum_type = firebird_dot_butler_dot_fbsd__pb2._DEPENDENCYTYPEENUM
_INTERFACEDESCRIPTOR.fields_by_name['requests'].message_type = _REQUESTCODE
_INSTALLEDSERVICE.fields_by_name['agent'].message_type = firebird_dot_butler_dot_fbsd__pb2._AGENTIDENTIFICATION
_INSTALLEDSERVICE.fields_by_name['api'].message_type = _INTERFACEDESCRIPTOR
_INSTALLEDSERVICE.fields_by_name['dependencies'].message_type = _DEPENDENCY
_INSTALLEDSERVICE.fields_by_name['service_type'].enum_type = _SERVICETYPEENUM
_INSTALLEDSERVICE.fields_by_name['mode'].enum_type = _EXECUTIONMODEENUM
_INSTALLEDSERVICE.fields_by_name['facilities'].enum_type = _SERVICEFACILITIESENUM
_INSTALLEDSERVICE.fields_by_name['supplement'].message_type = google_dot_protobuf_dot_any__pb2._ANY
_REPLYINSTALLEDSERVICES.fields_by_name['services'].message_type = _INSTALLEDSERVICE
_RUNNINGSERVICE.fields_by_name['peer'].message_type = firebird_dot_butler_dot_fbsd__pb2._PEERIDENTIFICATION
_RUNNINGSERVICE.fields_by_name['agent'].message_type = firebird_dot_butler_dot_fbsd__pb2._AGENTIDENTIFICATION
_RUNNINGSERVICE.fields_by_name['service_type'].enum_type = _SERVICETYPEENUM
_RUNNINGSERVICE.fields_by_name['mode'].enum_type = _EXECUTIONMODEENUM
_RUNNINGSERVICE.fields_by_name['facilities'].enum_type = _SERVICEFACILITIESENUM
_RUNNINGSERVICE.fields_by_name['config'].message_type = google_dot_protobuf_dot_struct__pb2._STRUCT
_RUNNINGSERVICE.fields_by_name['supplement'].message_type = google_dot_protobuf_dot_any__pb2._ANY
_REPLYRUNNINGSERVICES.fields_by_name['services'].message_type = _RUNNINGSERVICE
_REQUESTSTARTSERVICE.fields_by_name['config'].message_type = google_dot_protobuf_dot_struct__pb2._STRUCT
_REPLYSTARTSERVICE.fields_by_name['service'].message_type = _RUNNINGSERVICE
_REPLYSTOPSERVICE.fields_by_name['result'].enum_type = firebird_dot_butler_dot_fbsd__pb2._STATEENUM
DESCRIPTOR.message_types_by_name['Dependency'] = _DEPENDENCY
DESCRIPTOR.message_types_by_name['RequestCode'] = _REQUESTCODE
DESCRIPTOR.message_types_by_name['InterfaceDescriptor'] = _INTERFACEDESCRIPTOR
DESCRIPTOR.message_types_by_name['InstalledService'] = _INSTALLEDSERVICE
DESCRIPTOR.message_types_by_name['ReplyInstalledServices'] = _REPLYINSTALLEDSERVICES
DESCRIPTOR.message_types_by_name['RunningService'] = _RUNNINGSERVICE
DESCRIPTOR.message_types_by_name['ReplyRunningServices'] = _REPLYRUNNINGSERVICES
DESCRIPTOR.message_types_by_name['RequestInterfaceProviders'] = _REQUESTINTERFACEPROVIDERS
DESCRIPTOR.message_types_by_name['ReplyInterfaceProviders'] = _REPLYINTERFACEPROVIDERS
DESCRIPTOR.message_types_by_name['RequestStartService'] = _REQUESTSTARTSERVICE
DESCRIPTOR.message_types_by_name['ReplyStartService'] = _REPLYSTARTSERVICE
DESCRIPTOR.message_types_by_name['RequestStopService'] = _REQUESTSTOPSERVICE
DESCRIPTOR.message_types_by_name['ReplyStopService'] = _REPLYSTOPSERVICE
DESCRIPTOR.enum_types_by_name['ExecutionModeEnum'] = _EXECUTIONMODEENUM
DESCRIPTOR.enum_types_by_name['ServiceTypeEnum'] = _SERVICETYPEENUM
DESCRIPTOR.enum_types_by_name['ServiceFacilitiesEnum'] = _SERVICEFACILITIESENUM
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Dependency = _reflection.GeneratedProtocolMessageType('Dependency', (_message.Message,), dict(
  DESCRIPTOR = _DEPENDENCY,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.Dependency)
  ))
_sym_db.RegisterMessage(Dependency)

RequestCode = _reflection.GeneratedProtocolMessageType('RequestCode', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTCODE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.RequestCode)
  ))
_sym_db.RegisterMessage(RequestCode)

InterfaceDescriptor = _reflection.GeneratedProtocolMessageType('InterfaceDescriptor', (_message.Message,), dict(
  DESCRIPTOR = _INTERFACEDESCRIPTOR,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.InterfaceDescriptor)
  ))
_sym_db.RegisterMessage(InterfaceDescriptor)

InstalledService = _reflection.GeneratedProtocolMessageType('InstalledService', (_message.Message,), dict(
  DESCRIPTOR = _INSTALLEDSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.InstalledService)
  ))
_sym_db.RegisterMessage(InstalledService)

ReplyInstalledServices = _reflection.GeneratedProtocolMessageType('ReplyInstalledServices', (_message.Message,), dict(
  DESCRIPTOR = _REPLYINSTALLEDSERVICES,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.ReplyInstalledServices)
  ))
_sym_db.RegisterMessage(ReplyInstalledServices)

RunningService = _reflection.GeneratedProtocolMessageType('RunningService', (_message.Message,), dict(
  DESCRIPTOR = _RUNNINGSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.RunningService)
  ))
_sym_db.RegisterMessage(RunningService)

ReplyRunningServices = _reflection.GeneratedProtocolMessageType('ReplyRunningServices', (_message.Message,), dict(
  DESCRIPTOR = _REPLYRUNNINGSERVICES,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.ReplyRunningServices)
  ))
_sym_db.RegisterMessage(ReplyRunningServices)

RequestInterfaceProviders = _reflection.GeneratedProtocolMessageType('RequestInterfaceProviders', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTINTERFACEPROVIDERS,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.RequestInterfaceProviders)
  ))
_sym_db.RegisterMessage(RequestInterfaceProviders)

ReplyInterfaceProviders = _reflection.GeneratedProtocolMessageType('ReplyInterfaceProviders', (_message.Message,), dict(
  DESCRIPTOR = _REPLYINTERFACEPROVIDERS,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.ReplyInterfaceProviders)
  ))
_sym_db.RegisterMessage(ReplyInterfaceProviders)

RequestStartService = _reflection.GeneratedProtocolMessageType('RequestStartService', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSTARTSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.RequestStartService)
  ))
_sym_db.RegisterMessage(RequestStartService)

ReplyStartService = _reflection.GeneratedProtocolMessageType('ReplyStartService', (_message.Message,), dict(
  DESCRIPTOR = _REPLYSTARTSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.ReplyStartService)
  ))
_sym_db.RegisterMessage(ReplyStartService)

RequestStopService = _reflection.GeneratedProtocolMessageType('RequestStopService', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSTOPSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.RequestStopService)
  ))
_sym_db.RegisterMessage(RequestStopService)

ReplyStopService = _reflection.GeneratedProtocolMessageType('ReplyStopService', (_message.Message,), dict(
  DESCRIPTOR = _REPLYSTOPSERVICE,
  __module__ = 'saturnin.service.node.node_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.ReplyStopService)
  ))
_sym_db.RegisterMessage(ReplyStopService)


# @@protoc_insertion_point(module_scope)

from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

CHECK: Action
CITIZEN: Role
DESCRIPTOR: _descriptor.FileDescriptor
FAIL: Status
KILL: Action
MAFIA: Role
PUBLISH_DATA: Action
SHERIFF: Role
SUCCESS: Status
VOTE: Action

class ChooseRoomRequest(_message.Message):
    __slots__ = ["room"]
    ROOM_FIELD_NUMBER: _ClassVar[int]
    room: int
    def __init__(self, room: _Optional[int] = ...) -> None: ...

class GameRequest(_message.Message):
    __slots__ = ["message"]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class GameResponse(_message.Message):
    __slots__ = ["alive", "day", "info", "message", "response", "role", "winner"]
    ALIVE_FIELD_NUMBER: _ClassVar[int]
    DAY_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    WINNER_FIELD_NUMBER: _ClassVar[int]
    alive: _containers.RepeatedScalarFieldContainer[str]
    day: int
    info: Info
    message: str
    response: Response
    role: Role
    winner: Role
    def __init__(self, response: _Optional[_Union[Response, _Mapping]] = ..., message: _Optional[str] = ..., role: _Optional[_Union[Role, str]] = ..., day: _Optional[int] = ..., alive: _Optional[_Iterable[str]] = ..., info: _Optional[_Union[Info, _Mapping]] = ..., winner: _Optional[_Union[Role, str]] = ...) -> None: ...

class Info(_message.Message):
    __slots__ = ["action", "receive", "send"]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RECEIVE_FIELD_NUMBER: _ClassVar[int]
    SEND_FIELD_NUMBER: _ClassVar[int]
    action: Action
    receive: str
    send: str
    def __init__(self, action: _Optional[_Union[Action, str]] = ..., send: _Optional[str] = ..., receive: _Optional[str] = ...) -> None: ...

class MemberResponse(_message.Message):
    __slots__ = ["connected", "response", "unnamed"]
    CONNECTED_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    UNNAMED_FIELD_NUMBER: _ClassVar[int]
    connected: str
    response: Response
    unnamed: int
    def __init__(self, unnamed: _Optional[int] = ..., connected: _Optional[str] = ..., response: _Optional[_Union[Response, _Mapping]] = ...) -> None: ...

class Request(_message.Message):
    __slots__ = ["message"]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class Response(_message.Message):
    __slots__ = ["message", "room", "status"]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ROOM_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    message: str
    room: int
    status: Status
    def __init__(self, status: _Optional[_Union[Status, str]] = ..., message: _Optional[str] = ..., room: _Optional[int] = ...) -> None: ...

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

class Role(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

class Action(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

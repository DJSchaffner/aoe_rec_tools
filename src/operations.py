from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import struct
from typing import Self, Type, TypeVar


class PostgameType(Enum):
    WORLD_TIME = 1
    LEADERBOARDS = 2


class OperationType(Enum):
    ACTION = 1
    SYNC = 2
    VIEWLOCK = 3
    CHAT = 4
    START = 5  # We skip this because we parse the meta object at the start of operations
    POSTGAME = 6
    SAVE = 7


T = TypeVar("T", bound="Operation")


@dataclass
class Operation(ABC):
    data: bytes

    @classmethod
    def parse_operations(cls, raw_data: bytes) -> list[Self]:
        result: list[Operation] = []
        offset = 0

        while offset < len(raw_data):
            try:
                _type = OperationType(struct.unpack_from("<I", raw_data, offset)[0])
            except ValueError as error:
                raise ValueError(f"Failed to parse operation type because: {error}")

            offset += 4
            operation: Operation = None

            match _type:
                case OperationType.ACTION:
                    operation = ActionOperation.parse(raw_data, offset)
                case OperationType.SYNC:
                    operation = SyncOperation.parse(raw_data, offset)
                case OperationType.VIEWLOCK:
                    operation = ViewLockOperation.parse(raw_data, offset)
                case OperationType.CHAT:
                    operation = ChatOperation.parse(raw_data, offset)
                case OperationType.START:
                    operation = StartOperation.parse(raw_data, offset)
                case OperationType.POSTGAME:
                    operation = PostgameOperation.parse(raw_data, offset)
                case OperationType.SAVE:
                    operation = SaveOperation.parse(raw_data, offset)

            offset += operation.get_length_bytes()
            result.append(operation)

        return result

    @classmethod
    @abstractmethod
    def parse(cls: Type[T], raw_data: bytes, offset: int) -> T:
        raise NotImplementedError(f"{cls.__name__}.parse() must be overridden")

    @classmethod
    @abstractmethod
    def get_operation_type(cls) -> OperationType:
        raise NotImplementedError(f"{cls.__name__}.get_operation_type() must be overridden")

    def get_length_bytes(self) -> int:
        return len(self.data)

    def pack(self) -> bytes:
        return struct.pack("<I", self.get_operation_type().value) + self.data


class ActionOperation(Operation):
    ACTION_FORMAT = "<I"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        length, = struct.unpack_from(cls.ACTION_FORMAT, raw_data, offset)
        size = struct.calcsize(cls.ACTION_FORMAT) + length + 4

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.ACTION


class SyncOperation(Operation):
    SYNC_FORMAT_BASE = "<II"
    SYNC_FORMAT_EXTENDED = "<xxxxxxxxIII"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        size = 4
        _, unsigned = struct.unpack_from(cls.SYNC_FORMAT_BASE, raw_data, offset)

        # Sync operation can have a big unknown blob if the 4 bytes after time_increment are 0
        if unsigned == 0:
            _, _, sequence = struct.unpack_from(cls.SYNC_FORMAT_EXTENDED, raw_data, 4)
            size += struct.calcsize(cls.SYNC_FORMAT_EXTENDED)

            if sequence > 0:
                size += 332

            size += 8

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.SYNC


class ViewLockOperation(Operation):
    VIEWLOCK_FORMAT = "<ffI"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        size = struct.calcsize(cls.VIEWLOCK_FORMAT)

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.VIEWLOCK


class ChatOperation(Operation):
    VIEWLOCK_FORMAT = "<xxxxI"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        length, = struct.unpack_from(cls.VIEWLOCK_FORMAT, raw_data, offset)
        size = struct.calcsize(cls.VIEWLOCK_FORMAT) + length

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.CHAT


class StartOperation(Operation):
    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        raise Exception("Unexpected start operation encountered. Currently not supported")

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.START


class PostgameOperation(Operation):
    world_time: tuple[int, int]

    @dataclass
    class Player():
        player_id: int
        rank: int
        rating: int

        def pack(self) -> bytes:
            return struct.pack("<III", self.player_id, self.rank, self.rating)

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        return cls(raw_data[offset:])
        """Work in progress for real parsing
        # Postgame block is reversed and meta information is stored as big-endian (Credits to happyleaves for decoding this)
        data = io.BytesIO(raw_data[:offset:-1])
        data.read(8)
        version, num_blocks = struct.unpack(">II", data.read(8))

        for _ in range(num_blocks):
            identifier, length = struct.unpack(">II", data.read(8))
            postgame_type = PostgameType(identifier)

            # The block itself is not reversed and little endian again
            block = io.BytesIO(data.read()[::-1])
        """

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.POSTGAME


class SaveOperation(Operation):
    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        raise Exception("Unexpected save operation encountered. Currently not supported")

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.SAVE

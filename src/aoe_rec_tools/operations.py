from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import io
import struct
from typing import Self, Type, TypeVar


class OperationType(Enum):
    ACTION = 1
    SYNC = 2
    VIEW_LOCK = 3
    CHAT = 4
    START = 5
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
                case OperationType.VIEW_LOCK:
                    # ViewLock operations can be skipped so we can save time and space by dropping them
                    offset += ViewLockOperation.get_size()
                    continue
                    # operation = ViewLockOperation.parse(raw_data, offset)
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
    _FORMAT = "<I"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        length, = struct.unpack_from(cls._FORMAT, raw_data, offset)
        size = struct.calcsize(cls._FORMAT) + length + 4

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.ACTION


class SyncOperation(Operation):
    _FORMAT_BASE = "<II"
    _FORMAT_EXTENDED = "<xxxxxxxxIII"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        size = 4
        _, unsigned = struct.unpack_from(cls._FORMAT_BASE, raw_data, offset)

        # Sync operation can have a big unknown blob if the 4 bytes after time_increment are 0
        if unsigned == 0:
            _, _, sequence = struct.unpack_from(cls._FORMAT_EXTENDED, raw_data, 4)
            size += struct.calcsize(cls._FORMAT_EXTENDED)

            if sequence > 0:
                size += 332

            size += 8

        return cls(raw_data[offset:offset + size])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.SYNC


class ViewLockOperation(Operation):
    _FORMAT = "<ffI"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        return cls(raw_data[offset:offset + cls.get_size()])

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.VIEW_LOCK

    @classmethod
    def get_size(cls) -> int:
        return struct.calcsize(ViewLockOperation._FORMAT)


class ChatOperation(Operation):
    _FORMAT = "<xxxxI"

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        length, = struct.unpack_from(cls._FORMAT, raw_data, offset)
        size = struct.calcsize(cls._FORMAT) + length

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


@dataclass
class PostgameOperation(Operation):
    unknown: bytes
    version: int
    blocks: list["PostgameBlock"]

    class PostgameType(Enum):
        WORLD_TIME = 1
        LEADERBOARDS = 2

    @dataclass
    class PostgameBlock(ABC):
        identifier: int
        length: int

        def pack(self) -> bytes:
            return struct.pack(">II", self.identifier, self.length)

    @dataclass
    class WorldTimeBlock(PostgameBlock):
        _FORMAT = "<I"
        world_time: int

        def pack(self) -> bytes:
            body = struct.pack(self._FORMAT, self.world_time)
            return super().pack() + body[::-1]

    @dataclass
    class LeaderboardsBlock(PostgameBlock):
        num_leaderboards: int
        leaderboards: list["Leaderboard"]

        @dataclass
        class Leaderboard:
            _FORMAT = "<IHI"

            @dataclass
            class Player:
                _FORMAT = "<III"
                player_id: int
                rank: int
                rating: int

                @classmethod
                def parse(cls, data: io.BufferedReader):
                    return cls(*struct.unpack(cls._FORMAT, data.read(struct.calcsize(cls._FORMAT))))

                def pack(self) -> bytes:
                    return struct.pack(self._FORMAT, self.player_id, self.rank, self.rating)

            leaderboard_id: int
            unknown: int
            num_players: int
            players: list[Player]

            @classmethod
            def parse(cls, data: io.BufferedReader):
                leaderboard_id, unknown, num_players = struct.unpack(cls._FORMAT, data.read(struct.calcsize(cls._FORMAT)))
                players: list[PostgameOperation.LeaderboardsBlock.Player] = []

                for _ in range(num_players):
                    players.append(cls.Player.parse(data))

                return cls(leaderboard_id, unknown, num_players, players)

            def pack(self) -> bytes:
                return struct.pack(self._FORMAT, self.leaderboard_id, self.unknown, self.num_players) + b"".join(x.pack() for x in self.players)

        def pack(self) -> bytes:
            body = struct.pack("<I", self.num_leaderboards) + b"".join(x.pack() for x in self.leaderboards)
            return super().pack() + body[::-1]

    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        # Postgame block is reversed and meta information is stored as big-endian (Credits to happyleaves for decoding this)
        data = io.BytesIO(raw_data[offset:][::-1])
        unknown = data.read(8)
        version, num_blocks = struct.unpack(">II", data.read(8))
        blocks: list[PostgameOperation.PostgameBlock] = []

        for _ in range(num_blocks):
            identifier, length = struct.unpack(">II", data.read(8))
            postgame_type = cls.PostgameType(identifier)

            # The block itself is not reversed and little endian again
            block_data = io.BytesIO(data.read(length)[::-1])

            match postgame_type:
                case cls.PostgameType.WORLD_TIME:
                    world_time, = struct.unpack("<I", block_data.read(4))
                    block = cls.WorldTimeBlock(identifier, length, world_time)
                case cls.PostgameType.LEADERBOARDS:
                    num_leaderboards, = struct.unpack("<I", block_data.read(4))
                    leaderboards: list[PostgameOperation.LeaderboardsBlock] = []

                    for _ in range(num_leaderboards):
                        leaderboards.append(cls.LeaderboardsBlock.Leaderboard.parse(block_data))

                    block = cls.LeaderboardsBlock(identifier, length, num_leaderboards, leaderboards)

            blocks.append(block)

        return cls(raw_data, unknown, version, blocks)

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.POSTGAME

    def pack(self) -> bytes:
        packed_blocks = b"".join(block.pack() for block in self.blocks)
        header = self.unknown + struct.pack(">II", self.version, len(self.blocks))
        return (header + packed_blocks)[::-1]


class SaveOperation(Operation):
    @classmethod
    def parse(cls, raw_data: bytes, offset: int) -> Self:
        raise Exception("Unexpected save operation encountered. Currently not supported")

    @classmethod
    def get_operation_type(cls) -> OperationType:
        return OperationType.SAVE

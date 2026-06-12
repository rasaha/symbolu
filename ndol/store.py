"""Pluggable backing store.

The controller never touches hardware: it reads/writes opaque byte blobs
through this interface. The default `DictStore` keeps blobs in process RAM,
which is the correctness reference. A file/mmap/object-store backend can be
dropped in without changing any controller logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BackingStore(ABC):
    """A flat LBA → bytes store. Blobs may be compressed by the controller."""

    @abstractmethod
    def read(self, lba: int) -> bytes:
        ...

    @abstractmethod
    def write(self, lba: int, blob: bytes) -> None:
        ...

    @abstractmethod
    def exists(self, lba: int) -> bool:
        ...


class DictStore(BackingStore):
    """In-process reference store."""

    def __init__(self) -> None:
        self._d: dict[int, bytes] = {}

    def read(self, lba: int) -> bytes:
        return self._d.get(lba, b"")

    def write(self, lba: int, blob: bytes) -> None:
        self._d[lba] = blob

    def exists(self, lba: int) -> bool:
        return lba in self._d

    def __len__(self) -> int:
        return len(self._d)

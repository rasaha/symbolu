"""Pluggable backing store.

The controller never touches hardware: it reads/writes opaque byte blobs
through this interface. The default `DictStore` keeps blobs in process RAM,
which is the correctness reference. A file/mmap/object-store backend can be
dropped in without changing any controller logic.
"""
from __future__ import annotations

import mmap
import os
import struct
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


class FileStore(BackingStore):
    """Log-structured file backend — real OS storage, read via mmap.

    Blobs are appended to one data file (NAND is append + GC; overwrites orphan
    the old extent). An in-memory `lba → (offset, length)` index is the FTL map;
    it is persisted to a sidecar so the store survives across processes. mmap
    gives zero-copy reads. No special hardware — this runs on any filesystem.
    """

    _SIDECAR_MAGIC = b"NDOL01"

    def __init__(self, path: str) -> None:
        self.path = path
        self.index_path = path + ".idx"
        self._index: dict[int, tuple[int, int]] = {}
        self._f = open(path, "a+b")
        self._mm: mmap.mmap | None = None
        self._mapped_size = 0
        if os.path.exists(self.index_path):
            self._load_index()

    # --------------------------- index persistence ---------------------- #
    def _load_index(self) -> None:
        with open(self.index_path, "rb") as fh:
            if fh.read(len(self._SIDECAR_MAGIC)) != self._SIDECAR_MAGIC:
                return
            while chunk := fh.read(24):
                lba, off, length = struct.unpack("<qqq", chunk)
                self._index[lba] = (off, length)

    def flush_index(self) -> None:
        with open(self.index_path, "wb") as fh:
            fh.write(self._SIDECAR_MAGIC)
            for lba, (off, length) in self._index.items():
                fh.write(struct.pack("<qqq", lba, off, length))

    # --------------------------- mmap management ------------------------ #
    def _ensure_map(self) -> None:
        size = os.fstat(self._f.fileno()).st_size
        if size == 0:
            return
        if self._mm is None or self._mapped_size != size:
            if self._mm is not None:
                self._mm.close()
            self._mm = mmap.mmap(self._f.fileno(), size, access=mmap.ACCESS_READ)
            self._mapped_size = size

    # --------------------------- BackingStore --------------------------- #
    def write(self, lba: int, blob: bytes) -> None:
        self._f.seek(0, os.SEEK_END)
        offset = self._f.tell()
        self._f.write(blob)
        self._f.flush()
        self._index[lba] = (offset, len(blob))

    def read(self, lba: int) -> bytes:
        entry = self._index.get(lba)
        if entry is None:
            return b""
        off, length = entry
        self._ensure_map()
        assert self._mm is not None
        return bytes(self._mm[off : off + length])

    def exists(self, lba: int) -> bool:
        return lba in self._index

    def close(self) -> None:
        self.flush_index()
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        self._f.close()

    def __len__(self) -> int:
        return len(self._index)

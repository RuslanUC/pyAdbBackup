from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import AdbBackup
    from .backup import ProgressCb


class Partition:
    __slots__ = ("name", "path", "size", "_backup")

    def __init__(self, name: str, path: str, size: int, backup_: AdbBackup):
        self.name = name
        self.path = path
        self.size = size

        self._backup = backup_

    def size_mb(self) -> str:
        return f"{self.size / 1024 / 1024:.2f}"

    def backup(
            self, out_dir: Path, verify_checksum: bool = True, continue_: bool = True, skip_existing: bool = True,
            progress_callback: ProgressCb | None = None
    ) -> None:
        return self._backup.backup(self, out_dir, verify_checksum, continue_, skip_existing, progress_callback)

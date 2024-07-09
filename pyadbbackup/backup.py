import zlib
from pathlib import Path
from typing import Callable

from ppadb.connection import Connection
from ppadb.device import Device

from . import Partition, PartitionNotFound


ProgressCb = Callable[[int, Partition], None]


class AdbBackup:
    def __init__(self, device: Device):
        self._device = device

        self._part_block_size: int | None = None
        self._partitions = {}

    def _get_block_size(self) -> int:
        if not self._part_block_size:
            self._part_block_size = int(self._device.shell(
                "cat /sys/class/block/mmcblk0/queue/logical_block_size"
            ).strip())

        return self._part_block_size

    def _load_partitions(self) -> None:
        if self._partitions:
            return

        bs = self._get_block_size()
        lines = self._device.shell("ls -l /dev/block/bootdevice/by-name").splitlines()
        for line in lines:
            line = line.split(" ")
            if len(line) <= 2 or line[-2] != "->":
                continue
            name = line[-3]
            path = line[-1]
            blockname = path.split("/")[-1]
            size = int(self._device.shell(f"cat /sys/block/mmcblk0/{blockname}/size")) * bs

            self._partitions[name] = Partition(name, path, size)

    def list_partitions(self) -> list[Partition]:
        self._load_partitions()
        return list(self._partitions.values())

    def _get_compression_method(self) -> str | None:
        for comp in ("zstd", "gzip", "bzip2"):
            result = self._device.shell(f"{comp} --help")
            if "usage:" in result.lower():
                return comp

    def backup(self, partition: str | Partition, out_dir: Path, progress_callback: ProgressCb | None = None):
        if not isinstance(partition, Partition):
            name = partition
            self._load_partitions()
            if (partition := self._partitions.get(partition)) is None:
                raise PartitionNotFound(name)

        command = f"dd if={partition.path} bs=4M 2>/dev/null"
        if (comp_binary := self._get_compression_method()) is not None:
            command += f" | {comp_binary} -cf"

        def _handle(conn: Connection) -> None:
            transferred = 0
            dec = zlib.decompressobj(zlib.MAX_WBITS | 32)
            with open(out_dir / f"{partition.name}.img", "wb") as f:
                while data := conn.read(32 * 1024):
                    real = dec.decompress(data)
                    f.write(real)

                    transferred += len(real)
                    if progress_callback is not None:
                        progress_callback(transferred, partition)

            # TODO: raise proper exception
            # TODO: also check sha256sum
            assert transferred == partition.size
            conn.close()

        out_dir.mkdir(parents=True, exist_ok=True)
        self._device.shell(command, _handle)

import zlib
from hashlib import sha1
from pathlib import Path
from typing import Callable, BinaryIO

from ppadb.connection import Connection
from ppadb.device import Device

from . import Partition, PartitionNotFound, PartitionDataSizeMismatch, PartitionDataHashMismatch

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

            self._partitions[name] = Partition(name, path, size, self)

    def list_partitions(self) -> list[Partition]:
        self._load_partitions()
        return list(self._partitions.values())

    def _get_compression_method(self) -> str | None:
        for comp in ("zstd", "gzip", "bzip2"):
            result = self._device.shell(f"{comp} --help")
            if "usage:" in result.lower():
                return comp

    def _partition_checksum(self, partition: Partition, size: int | None = None) -> str:
        command = f"sha1sum {partition.path}" if size is None else f"head -c {size} {partition.path} | sha1sum"
        return self._device.shell(command).strip().split(" ")[0]

    @staticmethod
    def _localfile_checksum(file: Path) -> ...:
        sha = sha1()
        with open(file, "rb") as f:
            while data_ := f.read(4 * 1024 * 1024):
                sha.update(data_)

        return sha

    def backup(
            self, partition: str | Partition, out_dir: Path, verify_checksum: bool = True, continue_: bool = True,
            skip_existing: bool = True, progress_callback: ProgressCb | None = None,
    ):
        if not isinstance(partition, Partition):
            name = partition
            self._load_partitions()
            if (partition := self._partitions.get(partition)) is None:
                raise PartitionNotFound(name)

        tmp_file = out_dir / f"{partition.name}.tmp"
        out_file = out_dir / f"{partition.name}.img"
        device_sha = None

        if skip_existing and out_file.exists():
            return
        if not skip_existing and out_file.exists():
            device_sha = self._partition_checksum(partition)
            local_sha = self._localfile_checksum(out_file)
            if local_sha.hexdigest() == device_sha:
                return

        if not tmp_file.exists() or not continue_:
            continue_ = False
            tmp_file.unlink(True)

        command = f"dd if={partition.path}"

        continue_sha = None
        if continue_:
            filesize = tmp_file.stat().st_size
            part_sha = self._partition_checksum(partition, filesize)
            continue_sha = self._localfile_checksum(tmp_file)

            continue_ = continue_sha.hexdigest() == part_sha
            if continue_:
                command += f" bs={filesize} skip=1 2>/dev/null | dd"
            else:
                continue_sha = None

        command += f" bs=4M 2>/dev/null"
        if (comp_binary := self._get_compression_method()) is not None:
            command += f" | {comp_binary} -cf"

        def _handle(conn: Connection) -> None:
            nonlocal device_sha

            transferred = tmp_file.stat().st_size if continue_ else 0
            dec = zlib.decompressobj(zlib.MAX_WBITS | 32)
            sha = (continue_sha or sha1()) if verify_checksum else None
            f: BinaryIO
            with open(tmp_file, "ab" if continue_ else "wb") as f:
                while data := conn.read(32 * 1024):
                    real = dec.decompress(data)
                    f.write(real)

                    if verify_checksum:
                        sha.update(real)

                    transferred += len(real)
                    if progress_callback is not None:
                        progress_callback(transferred, partition)

            conn.close()

            if transferred != partition.size:
                raise PartitionDataSizeMismatch(partition.name, partition.size, transferred)
            if verify_checksum:
                device_sha = device_sha or self._partition_checksum(partition)
                if sha.hexdigest() != device_sha:
                    raise PartitionDataHashMismatch(partition.name, device_sha, sha.hexdigest())

            out_file.unlink(True)
            tmp_file.rename(out_file)

        out_dir.mkdir(parents=True, exist_ok=True)
        self._device.shell(command, _handle)

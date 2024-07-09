from pathlib import Path

from ppadb.client import Client

from pyadbbackup import Partition
from pyadbbackup.backup import AdbBackup

try:
    import click
except ImportError:
    click = None


ONLY_DIR = click.Path(file_okay=False, dir_okay=True, allow_dash=False, path_type=Path)

if click is not None:
    @click.command()
    @click.option("--adb-host", "-h", type=click.STRING, default="127.0.0.1", help="Adb server host.")
    @click.option("--adb-port", "-p", type=click.INT, default=5037, help="Adb server host.")
    @click.option("--list-devices", "-l", is_flag=True, default=False, help="List adb devices and exit.")
    @click.option("--list-partitions", "-i", is_flag=True, default=False, help="List device partitions.")
    @click.option("--device", "-d", type=click.STRING, default=None,
                  help="Specify adb device to work with. By default first device will be used.")
    @click.option("--partition", "-t", type=click.STRING, multiple=True, help="Specify partition to backup.")
    @click.option("--all", "-a", "backup_all", is_flag=True, default=False, help="Backup all partitions.")
    @click.option("--out", "-o", type=ONLY_DIR, default=Path("./"), help="Output directory.")
    @click.option("--verify-checksum", "-e", is_flag=True, default=True,
                  help="Verify partition checksum after backup.")
    @click.option("--continue/--no-continue", "-c", "continue_", is_flag=True, default=True,
                  help="Continue backup if it was interrupted. If partition data was changed, "
                       "backup will begin from start.")
    @click.option("--skip-existing/--no-skip-existing", "-s", is_flag=True, default=True,
                  help="Skip existing partition files if they already exist. If False and backup file exists, "
                       "backup will be skipped anyway if checksum will match to partition on device.")
    def main(
            adb_host: str, adb_port: int, list_devices: bool, list_partitions: bool, device: str | None,
            partition: list[str], backup_all: bool, out: Path, verify_checksum: bool, continue_: bool,
            skip_existing: bool,
    ) -> None:
        _main(
            adb_host, adb_port, list_devices, list_partitions, device, partition, backup_all, out, verify_checksum,
            continue_, skip_existing,
        )
else:
    def main(*args, **kwargs) -> None:
        print("Cli interface is disabled! Install \"click\" to enable cli support: \"pip install pyadbbackup[cli]\"")


def _main(
        adb_host: str, adb_port: int, list_devices: bool, list_partitions: bool, device: str | None,
        partition: list[str], backup_all: bool, out: Path, verify_checksum: bool, continue_: bool,
        skip_existing: bool,
) -> None:
    client = Client(host=adb_host, port=adb_port)
    devices = client.devices()

    if not devices:
        print("No devices found")
        return

    if list_devices:
        print("Connected devices:")
        for device in devices:
            print(device.serial)

        return

    device = client.device(device) if device else devices[0]
    backup = AdbBackup(device)

    if list_partitions:
        for part in backup.list_partitions():
            print(f"{part.name} - {part.path} - {part.size_mb()}MB")

    partitions = partition if not backup_all else backup.list_partitions()
    for partition in partitions:
        def _progress(read: int, part_: Partition):
            print(
                f"\rBacking up {part_.name}... {read / part_.size * 100:.2f}%",
                end="" if read != part_.size else "\n"
            )

        backup.backup(partition, out, verify_checksum, continue_, skip_existing, _progress)

    print("All done!")


if __name__ == '__main__':
    main()

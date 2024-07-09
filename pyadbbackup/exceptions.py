class PartitionNotFound(Exception):
    def __init__(self, name: str):
        super().__init__(f"Partition {name} not found.")
        self.partition_name = name


class PartitionDataSizeMismatch(Exception):
    def __init__(self, name: str, real_size: int, received_size: int):
        message = f"Partition {name} size mismatch: expected {real_size} bytes, got {received_size}."
        if real_size > received_size:
            message += (" If device was disconnected, try reconnecting it "
                        "and continuing backup with \"--continue\" flag.")
        super().__init__(message)

        self.partition_name = name
        self.real_size = real_size
        self.received_size = received_size


class PartitionDataHashMismatch(Exception):
    def __init__(self, name: str, real_hash: str, received_hash: str):
        super().__init__(f"Partition {name} hash mismatch: expected {real_hash} bytes, got {received_hash}.")
        self.partition_name = name
        self.real_hash = real_hash
        self.received_hash = received_hash

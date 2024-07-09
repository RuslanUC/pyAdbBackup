class PartitionNotFound(Exception):
    def __init__(self, name: str):
        super().__init__(f"Partition {name} not found")
        self.partition_name = name

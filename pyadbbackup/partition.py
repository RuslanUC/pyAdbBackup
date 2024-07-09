class Partition:
    def __init__(self, name: str, path: str, size: int):
        self.name = name
        self.path = path
        self.size = size

    def size_mb(self) -> str:
        return f"{self.size / 1024 / 1024:.2f}"

import os


class FileSystem:
    def makedirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def join(self, *parts: str) -> str:
        return os.path.join(*parts)

    def write_text(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

    def write_bytes(self, path: str, content: bytes) -> None:
        with open(path, "wb") as f:
            f.write(content)

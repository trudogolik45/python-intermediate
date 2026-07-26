from pathlib import Path

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"


class FileManager:
    def __init__(self, root=MEDIA_ROOT):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename, content):
        if self._is_file_exists(filename):
            return False
        (self.root / filename).write_bytes(content)
        return True

    def get_all_files(self):
        return sorted(path.name for path in self.root.iterdir() if path.is_file())

    def _is_file_exists(self, filename):
        return (self.root / filename).exists()


file_manager = FileManager()

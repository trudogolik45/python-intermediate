from pathlib import Path

from core.file.exceptions import FileAlreadyExistsError, InvalidFileNameError, UnsupportedFileTypeError
from file.managers import file_manager

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt"}


class FileService:
    @classmethod
    def save_file(cls, filename, content):
        safe_name = cls.build_safe_name(filename)
        if not file_manager.save_file(safe_name, content):
            raise FileAlreadyExistsError(safe_name)
        return safe_name

    @staticmethod
    def get_all_files():
        return file_manager.get_all_files()

    @staticmethod
    def build_safe_name(filename):
        name = Path(filename or "").name
        if not name or name.startswith("."):
            raise InvalidFileNameError(filename)
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(suffix)
        return name

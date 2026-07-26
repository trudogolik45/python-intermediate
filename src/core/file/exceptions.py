class FileError(Exception):
    pass


class FileAlreadyExistsError(FileError):
    def __init__(self, filename):
        super().__init__(f"File {filename} already exists")


class InvalidFileNameError(FileError):
    def __init__(self, filename):
        super().__init__(f"Invalid file name: {filename}")


class UnsupportedFileTypeError(FileError):
    def __init__(self, suffix):
        super().__init__(f"File type {suffix} is not supported")

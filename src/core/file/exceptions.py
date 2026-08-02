from core.exceptions import DomainError, Failure


class FileError(DomainError):
    pass


class FileAlreadyExistsError(FileError):
    failure = Failure.CONFLICT

    def __init__(self, filename):
        super().__init__(f"File {filename} already exists")


class InvalidFileNameError(FileError):
    failure = Failure.INVALID

    def __init__(self, filename):
        super().__init__(f"Invalid file name: {filename}")


class UnsupportedFileTypeError(FileError):
    failure = Failure.INVALID

    def __init__(self, suffix):
        super().__init__(f"File type {suffix} is not supported")

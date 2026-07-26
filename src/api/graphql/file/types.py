import strawberry

MEDIA_URL = "/media"


@strawberry.type
class UploadedFile:
    filename: str
    url: str


def to_uploaded_file(filename: str) -> UploadedFile:
    return UploadedFile(filename=filename, url=f"{MEDIA_URL}/{filename}")

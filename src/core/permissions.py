from enum import StrEnum


class Permission(StrEnum):
    VIEW_PRODUCT = "view_product"
    ADD_PRODUCT = "add_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    VIEW_USER = "view_user"
    VIEW_FILE = "view_file"
    UPLOAD_FILE = "upload_file"

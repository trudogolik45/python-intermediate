from enum import Enum


class Permission(str, Enum):
    VIEW_PRODUCT = "view_product"
    ADD_PRODUCT = "add_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    VIEW_USER = "view_user"

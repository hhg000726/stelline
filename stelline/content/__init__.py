"""관리자가 고칠 수 있는 사이트 문구·그림.

`registry`가 무엇을 고칠 수 있는지 정하고, `store`가 저장·조회를 맡는다.
`images`는 올린 파일이 정말 그 형식인지 표준 라이브러리만으로 확인한다.
"""

from stelline.content.registry import CONTENT_GROUPS, CONTENT_ITEMS, IMAGE, TEXT, get_item
from stelline.content.store import (
    ContentError,
    admin_rows,
    clear_item,
    load_image,
    reset_item,
    resolve_items,
    save_image,
    save_text,
)

__all__ = [
    "CONTENT_GROUPS",
    "CONTENT_ITEMS",
    "ContentError",
    "IMAGE",
    "TEXT",
    "admin_rows",
    "clear_item",
    "get_item",
    "load_image",
    "reset_item",
    "resolve_items",
    "save_image",
    "save_text",
]

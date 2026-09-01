"""관리자 화면의 사이트 문구·그림 편집.

표(`CONTENT_TABLES`)와 달리 여기는 **행이 아니라 항목**을 고친다. 무엇을 고칠 수 있는지는
`stelline/content/registry.py` 가 정하고, 저장·검증은 `stelline/content/store.py` 가 맡는다.
이 파일은 요청을 받아 넘기고 결과를 알려 주기만 한다.
"""

import logging

from flask import abort, flash, redirect, request, url_for

from stelline.admin.routes import admin_bp, login_required, require_csrf
from stelline.content import ContentError, IMAGE, TEXT, clear_item, get_item, reset_item, save_image, save_text


def _back_to(key):
    """고친 항목 자리로 되돌아간다. 항목이 서른 개 넘어 위에서 다시 찾으면 번거롭다."""
    return redirect(url_for("admin.admin_index") + "#content-" + key)


@admin_bp.route("/content/<key>", methods=["POST"])
@login_required
def save_content(key):
    require_csrf()
    item = get_item(key)
    if item is None:
        abort(404)

    action = request.form.get("action", "save")
    try:
        if action == "reset":
            reset_item(key)
            flash(f"{item['title']}을(를) 기본값으로 되돌렸습니다.", "success")
        elif action == "clear":
            clear_item(key)
            flash(f"{item['title']}을(를) 비웠습니다. 화면에서 그 자리가 사라집니다.", "success")
        elif item["type"] == TEXT:
            # 빈 칸을 보내면 "비움"이지만, 칸 자체가 없는 요청은 양식이 아니라 사고다.
            # 여기서 막지 않으면 잘못 만든 요청 하나가 화면의 문구를 지워 버린다.
            if "text" not in request.form:
                raise ContentError("문구 항목입니다. 내용 칸과 함께 보내야 합니다.")
            saved = save_text(key, request.form["text"])
            if saved:
                flash(f"{item['title']}을(를) 저장했습니다.", "success")
            else:
                flash(f"{item['title']}이(가) 비어 있어 화면에서 그 자리가 사라집니다.", "success")
        elif item["type"] == IMAGE:
            upload = request.files.get("image")
            # 상한보다 1바이트만 더 읽어 본다. 넘치는 파일을 통째로 메모리에 올리지 않는다.
            data = upload.read(item["max_bytes"] + 1) if upload else b""
            save_image(key, data)
            flash(f"{item['title']} 그림을 올렸습니다.", "success")
        else:
            abort(400)
    except ContentError as error:
        flash(f"{item['title']}: {error}", "error")
    except Exception:
        logging.exception("사이트 콘텐츠 저장 실패: %s", key)
        flash(f"{item['title']}을(를) 저장하지 못했습니다. 잠시 뒤 다시 시도하세요.", "error")
    return _back_to(key)

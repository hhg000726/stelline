from . import content_bp
from .service import fetch_site_content_image, fetch_site_contents


@content_bp.route("", methods=["GET"])
@content_bp.route("/", methods=["GET"])
def get_site_contents_api():
    return fetch_site_contents()


@content_bp.route("/image/<key>", methods=["GET"])
def get_site_content_image_api(key):
    return fetch_site_content_image(key)

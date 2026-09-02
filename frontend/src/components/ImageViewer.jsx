/* 안내 그림은 작게 늘어놓고, 누르면 원래 크기로 크게 본다.
 * 아무 데나 누르거나 Esc 로 닫는다(예전 search.js 의 attachImageViewer 와 같다).
 *
 * 떠 있는 동안 뒤 화면이 굴러가지 않게 하는 것과, 닫은 뒤 초점을 되돌리는 것은
 * 겹쳐 뜨는 창이 다 같이 지켜야 할 일이라 useModal 이 맡는다. */
import { useEffect, useRef } from "react";

import { useModal } from "../lib/useModal";

export function ImageViewer({ image, onClose }) {
  const closeButton = useRef(null);

  useModal(Boolean(image), onClose);

  // 열자마자 닫기 버튼에 초점을 둔다. 키보드만 쓰는 사람이 뒤 화면을 더듬지 않게 한다.
  useEffect(() => {
    if (image) closeButton.current?.focus();
  }, [image]);

  if (!image) return null;

  return (
    <div className="image-viewer" id="image-viewer" onClick={onClose}>
      <button type="button" className="image-viewer-close" aria-label="닫기" ref={closeButton}>
        ×
      </button>
      <img id="image-viewer-target" src={image.src} alt={image.alt || ""} />
    </div>
  );
}

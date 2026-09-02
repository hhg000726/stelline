/* 안내 그림은 작게 늘어놓고, 누르면 원래 크기로 크게 본다.
 * 아무 데나 누르거나 Esc 로 닫는다(예전 search.js 의 attachImageViewer 와 같다). */
import { useEffect } from "react";

export function ImageViewer({ image, onClose }) {
  useEffect(() => {
    if (!image) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [image, onClose]);

  if (!image) return null;

  return (
    <div className="image-viewer" id="image-viewer" onClick={onClose}>
      <button type="button" className="image-viewer-close" aria-label="닫기">
        ×
      </button>
      <img id="image-viewer-target" src={image.src} alt={image.alt || ""} />
    </div>
  );
}

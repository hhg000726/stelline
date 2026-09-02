/* 관리자 화면(사이트 문구·그림)에서 채우는 공지 칸.
 *
 * 제목·내용·그림이 모두 비어 있으면 이 칸 자체가 사라지므로, 기본 상태에서는
 * 아무 자리도 차지하지 않는다. (예전 data-content-block 규칙과 같다.)
 */
import { useContentItem } from "../context/ContentContext";
import { ContentText } from "./ContentText";

export function SiteNotice({ titleKey, textKey, imageKey }) {
  const title = useContentItem(titleKey);
  const text = useContentItem(textKey);
  const image = useContentItem(imageKey);

  const bodyVisible = !title.hidden || !text.hidden;
  if (!bodyVisible && image.hidden) return null;

  return (
    <div className="site-notice">
      {bodyVisible && (
        <div className="site-notice-body">
          <ContentText contentKey={titleKey} as="h2" className="site-notice-title" />
          <ContentText contentKey={textKey} as="p" className="site-notice-text" />
        </div>
      )}
      {!image.hidden && (
        <img className="site-notice-image" src={image.value} alt="" loading="lazy" />
      )}
    </div>
  );
}

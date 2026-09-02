/* 제목 줄이 있는 칸 하나.
 *
 * 화면마다 <div class="section-panel"> 짜임을 따로 적으면 머리말 모양이 조금씩
 * 어긋난다. 제목·설명·오른쪽 조작 자리를 한 곳에서 정한다.
 */
import { ContentText } from "./ContentText";

export function SectionPanel({ title, titleKey, noteKey, note, actions, full = false, className, children }) {
  const classNames = ["section-panel", full ? "is-full" : "", className].filter(Boolean).join(" ");
  return (
    <section className={classNames}>
      <div className="section-header">
        <div className="section-title">
          {titleKey ? <ContentText contentKey={titleKey} as="h2" /> : <h2>{title}</h2>}
          {noteKey ? <ContentText contentKey={noteKey} /> : note ? <p>{note}</p> : null}
        </div>
        {actions ? <div className="section-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

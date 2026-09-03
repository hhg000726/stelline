/* 관리자 화면에서 고치는 문구 한 자리.
 *
 * 값이 비면(관리자가 지웠거나 기본값이 없으면) 자리째 사라진다. 제목만 남고 빈 테두리가
 * 도는 일을 막으려는 것으로, 예전 content.js 의 data-content-key + hidden 과 같다.
 * 여러 줄 문구는 줄바꿈을 <br> 로 살리고, 목록형은 <li> 로 그린다.
 */
import { Fragment } from "react";

import { useContentItem } from "../context/ContentContext";

export function ContentText({ contentKey, as: Tag = "p", className, list = false, children }) {
  const item = useContentItem(contentKey);
  if (item.hidden) return null;

  if (list) {
    return (
      <Tag className={className}>
        {item.value.split("\n").map((line, index) => (
          <li key={`${index}-${line}`}>{line}</li>
        ))}
      </Tag>
    );
  }

  const lines = item.value.split("\n");
  return (
    <Tag className={className}>
      {lines.map((line, index) => (
        <Fragment key={`${index}-${line}`}>
          {index > 0 && <br />}
          {line}
        </Fragment>
      ))}
      {children}
    </Tag>
  );
}

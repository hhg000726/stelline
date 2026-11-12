/* 검색 정상화 방법 안내의 단계 그림.
 *
 * 관리자가 그림을 비우면 그 단계 칸이 통째로 사라지고 STEP 번호를 다시 매긴다.
 * (예전 content.js 의 data-content-hide=".stage" + renumberSteps 와 같은 규칙이다.)
 *
 * 기본 그림은 WebP 사본을 먼저 권한다(lib/webpCopies.js). 크게 볼 때는 칸에서 실제로 받은 파일
 * (currentSrc)을 그대로 띄워, 같은 그림을 다시 받지 않는다.
 */
import { useMemo } from "react";

import { ContentText } from "../../components/ContentText";
import { useContentItems } from "../../context/ContentContext";
import { webpCopyOf } from "../../lib/webpCopies";

export function StepGrid({ steps, onOpenImage, ...panelProps }) {
  const imageKeys = useMemo(() => steps.map((step) => step.imageKey), [steps]);
  const images = useContentItems(imageKeys);

  // 그림이 있는 단계만 남기고, 남은 것에만 차례로 번호를 준다.
  const visible = steps
    .map((step, index) => ({ step, image: images[index] }))
    .filter((entry) => !entry.image.hidden);

  return (
    <div className="step-grid" data-step-grid {...panelProps}>
      {visible.map((entry, index) => {
        const webp = webpCopyOf(entry.image.value);
        const open = (event) =>
          onOpenImage({ src: event.currentTarget.currentSrc || entry.image.value, alt: entry.step.alt });
        return (
          <div className="stage" key={entry.step.imageKey}>
            <div className="step-media">
              <picture>
                {webp ? <source srcSet={webp} type="image/webp" /> : null}
                <img
                  src={entry.image.value}
                  alt={entry.step.alt}
                  loading="lazy"
                  tabIndex={0}
                  role="button"
                  onClick={open}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      open(event);
                    }
                  }}
                />
              </picture>
            </div>
            <div className="step-copy">
              <span className="step-number" data-step-number>
                STEP {index + 1}
              </span>
              <ContentText contentKey={entry.step.labelKey} as="h3" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

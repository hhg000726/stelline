/* 검색 정상화 방법 안내의 단계 그림.
 *
 * 관리자가 그림을 비우면 그 단계 칸이 통째로 사라지고 STEP 번호를 다시 매긴다.
 * (예전 content.js 의 data-content-hide=".stage" + renumberSteps 와 같은 규칙이다.)
 */
import { useMemo } from "react";

import { ContentText } from "../../components/ContentText";
import { useContentItems } from "../../context/ContentContext";

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
        const open = () => onOpenImage({ src: entry.image.value, alt: entry.step.alt });
        return (
          <div className="stage" key={entry.step.imageKey}>
            <div className="step-media">
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
                    open();
                  }
                }}
              />
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

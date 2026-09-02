/* 이벤트·펀딩.
 *
 * 바깥 사이트로 나가는 자리는 버튼이 아니라 링크로 둔다. 그래야 새 탭으로 열거나
 * 주소를 미리 보는, 링크라면 당연히 되는 일들이 그대로 된다.
 */
import { useEffect, useState } from "react";

import { EmptyState } from "../../components/EmptyState";
import { SkeletonRows } from "../../components/Loading";
import { SectionPanel } from "../../components/SectionPanel";
import { api } from "../../lib/api";
import { toArray } from "../../lib/toArray";

export function EventsPanel() {
  const [state, setState] = useState({ status: "loading", items: [] });

  useEffect(() => {
    let alive = true;
    api("main/events", { method: "GET", headers: { "Content-Type": "application/json" } })
      .then((response) => response.json())
      .then((data) => {
        if (alive) setState({ status: "ready", items: toArray(data) });
      })
      .catch((error) => {
        console.error("이벤트 API 요청 중 오류 발생:", error);
        if (alive) setState({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  if (state.status === "ready" && !state.items.length) return null;

  return (
    <SectionPanel title="이벤트·펀딩" noteKey="main_events_note">
      <div id="button-container" className="button-grid">
        {state.status === "loading" && <SkeletonRows count={2} />}
        {state.status === "error" && <EmptyState isError>이벤트 정보를 불러오지 못했습니다.</EmptyState>}
        {state.status === "ready" &&
          state.items.map((event, index) => {
            const label = event.title || "이벤트";
            // 주소가 없는 <a> 는 눌리지도 초점이 가지도 않는다. 주소가 빠진 이벤트가
            // 눌리는 것처럼 보였다가 아무 일도 안 하는 것보다 낫다.
            const linkProps = event.link
              ? { href: event.link, target: "_blank", rel: "noopener noreferrer" }
              : {};
            return (
              <a className="btn-secondary" key={`${index}-${label}`} {...linkProps}>
                {label}
              </a>
            );
          })}
      </div>
    </SectionPanel>
  );
}

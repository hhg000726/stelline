/* 벅스 순위.
 *
 * 순위는 펼치지 않아도 보이는 편이 훨씬 쓸모 있어 접힌 줄에 함께 적는다.
 * 순위마다 할 말은 하나뿐이라, 예전처럼 빈 <p> 를 세 개 깔지 않고 그 하나만 그린다.
 */
import { useEffect, useState } from "react";

import { Collapse } from "../../components/Collapse";
import { EmptyState } from "../../components/EmptyState";
import { SkeletonRows } from "../../components/Loading";
import { SectionPanel } from "../../components/SectionPanel";
import { api } from "../../lib/api";
import { toArray } from "../../lib/toArray";

/* 윗등수와의 차이 한 줄. */
function rankGapText(rank, diffs = {}) {
  const votes = (count) => `${count ?? 0}표`;
  const share = (percent) => (percent ? ` / ${percent}%` : "");
  if (rank === 2) return `1등과의 차이: ${votes(diffs.count_to_first)}${share(diffs.streaming_to_first)}`;
  if (rank === 3) return `2등과의 차이: ${votes(diffs.count_to_second)}${share(diffs.streaming_to_second)}`;
  if (rank > 3) return `윗등수와의 차이: ${votes(diffs.count_diff)}${share(diffs.streaming_diff)}`;
  return "";
}

export function BugsPanel() {
  const [state, setState] = useState({ status: "loading", items: [] });
  const [openKey, setOpenKey] = useState(null);

  useEffect(() => {
    let alive = true;
    api("bugs/rank")
      .then((response) => response.json())
      .then((data) => {
        // 이름이 행 안에 없으면 객체의 키를 대신 쓴다(예전 index.js 와 같다).
        const names = data && typeof data === "object" && !Array.isArray(data) ? Object.keys(data) : [];
        const items = toArray(data)
          .filter(Boolean)
          .map((entry, index) => ({
            ...entry,
            name: entry.name || names[index] || `대상${index + 1}`,
          }));
        if (alive) setState({ status: "ready", items });
      })
      .catch((error) => {
        console.error("벅스 데이터 로드 실패:", error);
        if (alive) setState({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  if (state.status === "ready" && !state.items.length) return null;

  return (
    <SectionPanel title="벅스 순위" noteKey="main_bugs_note">
      <div id="bugs" className="stack-list">
        {state.status === "loading" && <SkeletonRows count={2} />}
        {state.status === "error" && <EmptyState isError>벅스 순위를 불러오지 못했습니다.</EmptyState>}
        {state.status === "ready" &&
          state.items.map((entry) => {
            const contentId = `hiddenContent_bug_${String(entry.name).replace(/\s+/g, "_")}`;
            const open = openKey === contentId;
            const gap = rankGapText(entry.rank, entry.diffs || {});
            return (
              <div key={contentId}>
                <button
                  type="button"
                  className={`toggle-button btn-secondary${open ? " is-open" : ""}`}
                  aria-expanded={open}
                  aria-controls={contentId}
                  onClick={() => setOpenKey(open ? null : contentId)}
                >
                  <span>
                    벅스 {entry.name}
                    {entry.title ? ` · ${entry.title}` : ""}
                  </span>
                  {entry.rank ? <span className="toggle-meta">현재 {Number(entry.rank)}위</span> : null}
                </button>
                <Collapse id={contentId} open={open}>
                  <div className="list-item-content">
                    <div className="list-item-body">
                      <strong>현재 {Number(entry.rank) || 0}위</strong>
                      {gap ? <p>{gap}</p> : null}
                      <p>매일 계정마다 하트 100개를 무료로 줍니다</p>
                      <p>계정은 같은 번호로 3개까지 만들 수 있습니다</p>
                      <p>광고를 시청하여 하트를 얻을 수도 있습니다</p>
                      <a
                        className="btn-secondary"
                        href={`https://favorite.bugs.co.kr/${encodeURIComponent(entry.url_number || "")}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        벅스 바로가기
                      </a>
                    </div>
                  </div>
                </Collapse>
              </div>
            );
          })}
      </div>
    </SectionPanel>
  );
}

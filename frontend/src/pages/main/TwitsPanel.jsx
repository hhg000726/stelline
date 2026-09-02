/* 트윗 안내.
 *
 * 총공 시간은 펼치기 전에도 보여야 "언제 하는지"를 바로 알 수 있다.
 * 복사 & 새 탭은 예전 index.js 의 copyText 와 같은 순서로 움직인다.
 */
import { useEffect, useState } from "react";

import { Collapse } from "../../components/Collapse";
import { EmptyState } from "../../components/EmptyState";
import { SkeletonRows } from "../../components/Loading";
import { SectionPanel } from "../../components/SectionPanel";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { copyText } from "../../lib/clipboard";
import { openExternal } from "../../lib/openExternal";
import { toArray } from "../../lib/toArray";

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function TwitsPanel() {
  const [state, setState] = useState({ status: "loading", items: [] });
  const [openIndex, setOpenIndex] = useState(null);
  const toast = useToast();

  useEffect(() => {
    let alive = true;
    api("main/twits")
      .then((response) => response.json())
      .then((data) => {
        if (alive) setState({ status: "ready", items: toArray(data) });
      })
      .catch((error) => {
        console.error("트윗 데이터 로드 실패:", error);
        if (alive) setState({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  // 값이 하나도 없으면 칸째 사라진다(예전에도 panel.hidden 이었다).
  if (state.status === "ready" && !state.items.length) return null;

  async function onCopy(text) {
    api("main/record", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    }).catch((error) => console.error("API 요청 중 오류 발생:", error));

    // 복사에 실패하면 X로 보내 봐야 붙여 넣을 것이 없다. 그대로 두고 까닭을 알린다.
    if (!(await copyText(text))) {
      toast("복사하지 못했어요. 키워드를 직접 선택해 복사해 주세요.");
      return;
    }

    // 보던 화면은 그대로 두고 새 탭만 연다.
    // (이 창에서 넘어가 버리면 읽던 안내가 사라진다. 복사는 이미 끝나 있으니
    //  주소창에 직접 붙여 넣을 수도 있다.)
    if (openExternal("https://x.com/")) {
      toast("복사했어요. 새 탭에서 X를 열었습니다.");
    } else {
      toast("복사했어요. 새 탭이 열리지 않았다면 팝업 차단을 확인해 주세요.");
    }
  }

  return (
    <SectionPanel title="트윗 안내" noteKey="main_twits_note" full>
      <div id="twitContainer" className="stack-list">
        {state.status === "loading" && <SkeletonRows count={2} />}
        {state.status === "error" && <EmptyState isError>트윗 안내를 불러오지 못했습니다.</EmptyState>}
        {state.status === "ready" &&
          state.items.map((item, index) => {
            const keywords = splitList(item.keywords);
            const tags = splitList(item.tags);
            const open = openIndex === index;
            const panelId = `hiddenContent_twit_${index}`;
            const time = String(item.time || "").trim();

            return (
              <div key={panelId}>
                <button
                  type="button"
                  className={`toggle-button btn-secondary${open ? " is-open" : ""}`}
                  aria-expanded={open}
                  aria-controls={panelId}
                  onClick={() => setOpenIndex(open ? null : index)}
                >
                  <span>{item.title || `트윗 안내 ${index + 1}`}</span>
                  <span className="toggle-meta">{time || "임시 연기"}</span>
                </button>
                <Collapse id={panelId} open={open}>
                  <div className="list-item-content">
                    <div className="list-item-body">
                      <p>태그와 키워드를 사용하여 트윗 작성</p>
                      <p>태그 검색 후 다른 트윗 리트윗 &amp; 좋아요 누르기</p>
                      <p>
                        시간상 참여가 어려우신 분들은 예약 트윗을 활용해주세요.
                        <br />
                        같은 내용의 트윗은 중복 작성되지 않습니다.
                        <br />
                        하고 싶은 말 부분을 필수로 작성해주시기 바랍니다.
                      </p>
                    </div>
                    <h3 className="copy-grid-title">태그 &amp; 키워드</h3>
                    <div className="copy-grid">
                      {keywords.map((keyword, keywordIndex) => {
                        const value = [keyword, ...tags.map((tag) => `#${tag}`)].join("\n");
                        return (
                          <div className="copy-card" key={`${keywordIndex}-${keyword}`}>
                            <div className="copy-card-top">
                              <div className="copy-card-kicker">키워드</div>
                            </div>
                            <p className="copy-text">
                              <strong>{keyword}</strong>
                            </p>
                            <div className="tag-list">
                              {tags.map((tag) => (
                                <span className="tag-chip" key={tag}>
                                  #{tag}
                                </span>
                              ))}
                            </div>
                            <button
                              type="button"
                              className="btn-primary copy-button"
                              onClick={() => onCopy(value)}
                            >
                              복사 &amp; 새 탭
                            </button>
                          </div>
                        );
                      })}
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

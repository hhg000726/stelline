/* 같은 칸 안에서 목록을 바꿔 보여 주는 탭.
 *
 * role="tab" 을 붙여 둔 이상 탭처럼 움직여야 한다. 탭과 칸을 aria 로 이어 주고,
 * 좌우 화살표로도 옮겨 다닐 수 있게 한다. (화살표가 없으면 화면 낭독기 사용자는
 * 탭이라 안내받고도 넘길 수가 없다.) 탭 묶음은 통째로 한 번만 Tab 키에 걸린다.
 */
import { useRef } from "react";

export function tabId(groupId, name) {
  return `${groupId}-tab-${name}`;
}

export function panelId(groupId, name) {
  return `${groupId}-panel-${name}`;
}

/* 탭이 다스리는 칸에 그대로 펼쳐 넣는 속성. */
export function tabPanelProps(groupId, name, active) {
  return {
    id: panelId(groupId, name),
    role: "tabpanel",
    "aria-labelledby": tabId(groupId, name),
    hidden: !active,
  };
}

export function Segmented({ groupId, label, tabs, value, onChange, className = "segmented" }) {
  const nodes = useRef([]);

  function onKeyDown(event, index) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + tabs.length) % tabs.length;
    onChange(tabs[next].name);
    nodes.current[next]?.focus();
  }

  return (
    <div className={className} id={groupId} role="tablist" aria-label={label}>
      {tabs.map((tab, index) => {
        const active = tab.name === value;
        return (
          <button
            key={tab.name}
            ref={(node) => {
              nodes.current[index] = node;
            }}
            id={tabId(groupId, tab.name)}
            type="button"
            role="tab"
            className={active ? "is-on" : undefined}
            aria-selected={active}
            aria-controls={panelId(groupId, tab.name)}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.name)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {tab.label}
            {tab.suffix}
          </button>
        );
      })}
    </div>
  );
}

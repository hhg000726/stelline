/* 알림 말풍선.
 *
 * 복사처럼 화면이 그대로인 동작은 알려 주지 않으면 눌렸는지조차 알 수 없다.
 * 화면마다 따로 만들면 위치와 사라지는 시간이 어긋나므로 앱 전체에서 하나만 쓴다.
 * (예전 assets/site.js 의 toast 와 같은 시간·모양이다.)
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const VISIBLE_MS = 1800;
const FADE_MS = 200;

const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  // seq 는 같은 문구를 연달아 띄워도 다시 나타나게 하는 값이다.
  const [state, setState] = useState({ message: "", seq: 0 });
  const [visible, setVisible] = useState(false);
  const node = useRef(null);
  const timers = useRef([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const toast = useCallback((text) => {
    if (!text) return;
    clearTimers();
    setVisible(false);
    setState((prev) => ({ message: text, seq: prev.seq + 1 }));
  }, [clearTimers]);

  /* hidden 을 막 벗겨낸 프레임에 클래스를 같이 붙이면 전환이 생략된다.
   * 배치를 한 번 읽어 강제로 반영시킨 뒤에 붙인다. (requestAnimationFrame 은 탭이
   * 가려져 있으면 아예 실행되지 않아, 말풍선이 투명한 채로 사라지는 일이 생긴다.) */
  useEffect(() => {
    if (!state.message || !node.current) return undefined;
    void node.current.offsetWidth;
    setVisible(true);
    const hide = window.setTimeout(() => setVisible(false), VISIBLE_MS);
    const clear = window.setTimeout(() => setState((prev) => ({ ...prev, message: "" })), VISIBLE_MS + FADE_MS);
    timers.current.push(hide, clear);
    return undefined;
  }, [state.seq, state.message]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {/* 스스로 읽어 주되, 말풍선이 뜨기 전의 빈 상태를 읽지는 않게 한다. */}
      <div
        ref={node}
        className={`site-toast${visible ? " is-visible" : ""}`}
        id="site-toast"
        role="status"
        aria-live="polite"
        hidden={!state.message}
      >
        {state.message}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

/* 사용자 제보 칸. 검색·노래방·조회수 축하 세 화면이 같은 짜임을 쓴다.
 *
 * 보내는 형식(POST { content, captcha_token })과 서버가 돌려주는 message/error 처리는
 * 예전과 똑같다. 달라진 것은 알려 주는 방식뿐이다.
 *   - 캡차 스크립트를 화면을 열 때가 아니라 제보 칸을 펼칠 때 받아 온다.
 *   - 글자 수와 빈 칸을 치는 동안 알려 준다(보내고 나서야 알게 되지 않는다).
 *   - 보내는 동안 버튼을 잠가 두 번 눌리지 않게 한다.
 *
 * 여닫는 일은 Collapse 가 맡는다. 예전에는 `hidden` 을 붙였다 떼었다. 칸이 한 프레임에
 * 통째로 나타나 아래 목록이 그만큼 튀어 올랐고, 제목 줄 안에서 열리는 바람에 좁은
 * 세로 기둥에 양식이 구겨져 들어갔다. 이제 벅스·트윗 칸과 같은 방식으로 밀어 올리고,
 * 열린 칸은 제목 줄 아래 한 줄을 통째로 쓴다(site.css 의 .hero-heading 참고).
 */
import { useEffect, useId, useRef, useState } from "react";

import { submitReport } from "../lib/api";
import { loadScript } from "../lib/loadScript";
import { Collapse } from "./Collapse";
import { Icon } from "./Icon";
import { Spinner } from "./Loading";

const TURNSTILE_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const SITE_KEY = "0x4AAAAAAEgvGwCT4Q867aaL";
// 서버(stelline/apis/reports.py)의 MAX_REPORT_LENGTH 와 같은 값이다.
const MAX_LENGTH = 2000;
// 다 열리기를 기다렸다가 화면을 맞추는 시간. app.css 의 .report-collapse 와 같은 길이다.
const OPEN_MS = 360;

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export function ReportPanel({
  endpoint,
  openLabel,
  closeLabel,
  title,
  description,
  fieldLabel,
  placeholder,
  submitLabel,
}) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState({ text: "", tone: "" });

  const toggle = useRef(null);
  const panel = useRef(null);
  const textarea = useRef(null);
  const captchaBox = useRef(null);
  const widget = useRef(undefined);
  const baseId = useId();
  const fieldId = `${baseId}-field`;
  const panelId = `${baseId}-panel`;
  const titleId = `${baseId}-title`;

  const tooLong = content.length > MAX_LENGTH;
  const empty = !content.trim();

  /* 캡차는 제보 칸을 펼친 뒤에 한 번만 그린다. 예전에는 화면에 들어오기만 해도
     스크립트를 받아 왔는데, 제보를 쓰지 않는 사람에게는 쓸모없는 요청이었다. */
  useEffect(() => {
    if (!open) return;
    let alive = true;
    loadScript(TURNSTILE_SRC)
      .then(() => {
        if (!alive || !captchaBox.current || widget.current !== undefined) return;
        if (!window.turnstile) return;
        widget.current = window.turnstile.render(captchaBox.current, { sitekey: SITE_KEY });
      })
      .catch(() => {
        if (alive) setStatus({ text: "캡차를 불러오지 못했습니다. 잠시 후 다시 시도하세요.", tone: "is-error" });
      });
    return () => {
      alive = false;
    };
  }, [open]);

  /* 초점을 옮기는 일은 칸이 다 열린 뒤로 미루지 않는다(글을 쓰러 온 사람을 기다리게 한다).
   * 다만 브라우저가 초점을 따라 화면을 확 끌어당기면 열리는 동작이 통째로 건너뛴 것처럼
   * 보이므로, 자리 이동은 막아 두고 다 열린 뒤에 화면 밖으로 밀려난 경우에만 끌어온다. */
  useEffect(() => {
    if (!open) return undefined;
    textarea.current?.focus({ preventScroll: true });
    const timer = window.setTimeout(() => {
      const node = panel.current;
      if (!node) return;
      const box = node.getBoundingClientRect();
      if (box.top >= 0 && box.bottom <= window.innerHeight) return;
      node.scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }, OPEN_MS);
    return () => window.clearTimeout(timer);
  }, [open]);

  /* 펼쳐 둔 칸을 접을 때 손이 있는 자리(칸 안)에서 바로 접을 수 있어야 한다.
   * 접고 나면 초점이 사라진 칸에 남지 않도록 눌렀던 버튼으로 되돌린다. 쓰던 글은 그대로 둔다. */
  function onPanelKeyDown(event) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    setOpen(false);
    toggle.current?.focus();
  }

  async function onSubmit(event) {
    event.preventDefault();
    const value = content.trim();
    if (!value || tooLong || sending) return;

    const captchaToken = window.turnstile?.getResponse(widget.current);
    if (!captchaToken) {
      setStatus({ text: "캡차 인증을 완료하세요.", tone: "is-error" });
      return;
    }

    setSending(true);
    setStatus({ text: "보내는 중...", tone: "" });
    try {
      const message = await submitReport(endpoint, value, captchaToken);
      setContent("");
      setStatus({ text: message, tone: "is-success" });
    } catch (error) {
      setStatus({ text: error.message, tone: "is-error" });
    } finally {
      setSending(false);
      window.turnstile?.reset(widget.current);
    }
  }

  return (
    <>
      {/* 여는 말과 닫는 말을 같은 자리에 겹쳐 둔다. 둘 중 긴 쪽이 버튼 너비를 정하므로
          여닫을 때마다 버튼이 늘었다 줄었다 하며 제목 줄을 밀지 않는다.
          겹쳐 둔 글자를 읽어 주는 프로그램이 둘 다 읽거나(또는 아무것도 읽지 못하고)
          헤매지 않도록, 지금 보이는 쪽을 이름으로 못 박아 둔다. */}
      <button
        ref={toggle}
        className={`btn-secondary report-toggle${open ? " is-open" : ""}`}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? closeLabel : openLabel}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="report-toggle-labels">
          <span className={`report-toggle-label${open ? "" : " is-shown"}`} aria-hidden={open || undefined}>
            {openLabel}
          </span>
          <span className={`report-toggle-label${open ? " is-shown" : ""}`} aria-hidden={!open || undefined}>
            {closeLabel}
          </span>
        </span>
        <Icon name="chevron" className="report-toggle-caret" />
      </button>

      {/* 칸을 접었다고 없애 버리면 캡차 위젯도 함께 사라져, 다시 펼칠 때마다 새로 그려야 한다.
          Collapse 는 자리만 접고 내용은 문서에 남긴다(접힌 동안에는 inert 라 Tab 도 들어가지 않는다). */}
      <Collapse id={panelId} open={open} className="report-collapse">
        <div
          ref={panel}
          className="report-panel"
          role="group"
          aria-labelledby={titleId}
          onKeyDown={onPanelKeyDown}
        >
          <div className="report-panel-head">
            <h2 id={titleId}>{title}</h2>
            <p>{description}</p>
          </div>
          <form onSubmit={onSubmit}>
            <div className="report-field">
              <label htmlFor={fieldId}>{fieldLabel}</label>
              <textarea
                id={fieldId}
                ref={textarea}
                className={tooLong ? "is-invalid" : undefined}
                maxLength={MAX_LENGTH}
                rows={4}
                placeholder={placeholder}
                required
                value={content}
                onChange={(event) => setContent(event.target.value)}
              />
              <p className="field-note">
                <span>{empty ? "보내려면 내용을 입력하세요." : ""}</span>
                <span className={tooLong ? "is-over" : undefined}>
                  {content.length}/{MAX_LENGTH}자
                </span>
              </p>
            </div>
            <div ref={captchaBox} className="cf-turnstile" />
            <div className="report-actions">
              <span className={`meta-text ${status.tone}`.trim()} role="status">
                {status.text}
              </span>
              <button className="btn-primary" type="submit" disabled={sending || empty || tooLong}>
                {sending ? (
                  <>
                    <Spinner /> 보내는 중
                  </>
                ) : (
                  submitLabel
                )}
              </button>
            </div>
          </form>
        </div>
      </Collapse>
    </>
  );
}

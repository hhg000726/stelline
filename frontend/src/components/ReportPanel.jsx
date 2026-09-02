/* 사용자 제보 칸. 검색·노래방·조회수 축하 세 화면이 같은 짜임을 쓴다.
 *
 * 보내는 형식(POST { content, captcha_token })과 서버가 돌려주는 message/error 처리는
 * 예전과 똑같다. 달라진 것은 알려 주는 방식뿐이다.
 *   - 캡차 스크립트를 화면을 열 때가 아니라 제보 칸을 펼칠 때 받아 온다.
 *   - 글자 수와 빈 칸을 치는 동안 알려 준다(보내고 나서야 알게 되지 않는다).
 *   - 보내는 동안 버튼을 잠가 두 번 눌리지 않게 한다.
 */
import { useEffect, useId, useRef, useState } from "react";

import { submitReport } from "../lib/api";
import { loadScript } from "../lib/loadScript";
import { Spinner } from "./Loading";

const TURNSTILE_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const SITE_KEY = "0x4AAAAAAEgvGwCT4Q867aaL";
// 서버(stelline/apis/reports.py)의 MAX_REPORT_LENGTH 와 같은 값이다.
const MAX_LENGTH = 2000;

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

  const textarea = useRef(null);
  const captchaBox = useRef(null);
  const widget = useRef(undefined);
  const fieldId = useId();

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

  useEffect(() => {
    if (open) textarea.current?.focus();
  }, [open]);

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
      <button
        className="btn-secondary report-toggle"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        {open ? closeLabel : openLabel}
      </button>

      {/* 칸을 접었다고 없애 버리면 캡차 위젯도 함께 사라져, 다시 펼칠 때마다 새로 그려야 한다.
          예전처럼 자리만 감춘다. */}
      <div className="report-panel" hidden={!open}>
        <h2>{title}</h2>
        <p>{description}</p>
        <form onSubmit={onSubmit}>
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
    </>
  );
}

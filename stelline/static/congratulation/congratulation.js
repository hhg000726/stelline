async function fetchSongs() {
    try {
        const response = await Stelline.api('congratulation/congratulations');
        const data = await response.json();
        data.sort((a, b) => new Date(b.counted_time) - new Date(a.counted_time));
        renderTable(data, "congratulationTable");
    } catch (error) {
        console.error('Error fetching songs:', error);
        const container = document.getElementById("congratulationTable");
        if (container) {
            container.innerHTML = '<p class="empty-state is-error">기록을 불러오지 못했습니다.</p>';
        }
    }
}

function attachReportForm() {
  const toggle = document.getElementById("report-toggle");
  const panel = document.getElementById("report-panel");
  const form = document.getElementById("report-form");
  const content = document.getElementById("report-content");
  const status = document.getElementById("report-status");
  const captchaContainer = document.getElementById("report-captcha");
  let captchaWidget;
  if (!toggle || !panel || !form) return;

  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    toggle.textContent = panel.hidden ? "누락된 노래 제보" : "제보 입력 닫기";
    if (!panel.hidden) {
      content.focus();
      if (captchaContainer && window.turnstile && captchaWidget === undefined) {
        captchaWidget = window.turnstile.render(captchaContainer, {
          sitekey: "0x4AAAAAAEgvGwCT4Q867aaL"
        });
      }
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = content.value.trim();
    if (!value) return;
    const captchaToken = window.turnstile?.getResponse(captchaWidget);
    if (!captchaToken) {
      status.textContent = "캡차 인증을 완료하세요.";
      return;
    }
    status.textContent = "보내는 중...";
    try {
      const response = await Stelline.api("congratulation/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: value, captcha_token: captchaToken })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "제보를 보내지 못했습니다.");
      form.reset();
      status.textContent = result.message;
      window.turnstile?.reset(captchaWidget);
    } catch (error) {
      status.textContent = error.message;
      window.turnstile?.reset(captchaWidget);
    }
  });
}

function renderTable(data, tableId) {
  const container = document.getElementById(tableId);
  const resultsCount = document.getElementById('resultsCount');

  if (!container) {
    return;
  }

  container.innerHTML = "";
  if (resultsCount) {
    resultsCount.textContent = `${data.length}개 기록`;
  }

  if (data.length === 0) {
    const note = document.createElement("p");
    note.className = "empty-state";
    note.textContent = "최근 24시간 이내 달성 기록이 아직 없습니다.";
    container.appendChild(note);
    return;
  }

  data.forEach((song, index) => {
    const card = document.createElement("article");
    card.className = "card";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "thumb-wrap";

    const badge = document.createElement("span");
    badge.className = "card-badge";
    badge.textContent = `#${data.length - index}`;

    const img = document.createElement("img");
    img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
    img.alt = "영상 썸네일";
    img.loading = "lazy";

    thumbWrap.appendChild(badge);
    thumbWrap.appendChild(img);
    card.appendChild(thumbWrap);

    const info = document.createElement("div");
    info.className = "info";

    const meta = document.createElement("div");
    meta.className = "meta";

    const reached = document.createElement("span");
    reached.textContent = ``;

    const time = document.createElement("span");
    const diff = Date.now() - new Date(song.counted_time).getTime();
    const hours = Math.floor(diff / 3600000);
    time.textContent = hours > 0 ? `${hours}시간 전` : "방금 전";

    meta.appendChild(reached);
    meta.appendChild(time);
    info.appendChild(meta);

    const title = document.createElement("p");
    title.textContent = song.title || "조회수 달성";
    info.appendChild(title);

    const summary = document.createElement("h3");
    summary.textContent = `${Math.floor(song.count / 100000)}0만 달성`;
    info.appendChild(summary);

    const cta = document.createElement("div");
    cta.className = "cta";

    const button = document.createElement("button");
    button.className = "btn-primary";
    button.type = "button";
    button.innerHTML = Stelline.icon("play") + " 유튜브로 이동";
    button.onclick = () => handleButtonClick(song.video_id);

    cta.appendChild(button);
    info.appendChild(cta);

    card.appendChild(info);
    container.appendChild(card);
  });
}

function handleButtonClick(video_id) {
    window.location.href = `https://www.youtube.com/watch?v=${video_id}`;
}

document.addEventListener("DOMContentLoaded", fetchSongs);
document.addEventListener("DOMContentLoaded", attachReportForm);

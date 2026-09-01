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

  data.forEach((song) => {
    // 카드 전체가 "유튜브로 이동" 버튼이라 버튼 줄을 따로 두지 않는다.
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card is-link";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "thumb-wrap";

    // 배지에는 순번 대신 달성 기록을 넣는다. 목록에서 바로 읽히는 값이다.
    const badge = document.createElement("span");
    badge.className = "card-badge";
    badge.textContent = `${Math.floor(song.count / 100000)}0만`;

    const img = document.createElement("img");
    img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
    img.alt = "";
    img.loading = "lazy";

    const play = document.createElement("span");
    play.className = "thumb-play";
    play.innerHTML = Stelline.icon("play");

    thumbWrap.appendChild(badge);
    thumbWrap.appendChild(img);
    thumbWrap.appendChild(play);
    card.appendChild(thumbWrap);

    const info = document.createElement("div");
    info.className = "info";

    const title = document.createElement("h3");
    title.textContent = song.title || "조회수 달성";
    info.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "meta";

    const time = document.createElement("span");
    const diff = Date.now() - new Date(song.counted_time).getTime();
    const hours = Math.floor(diff / 3600000);
    time.textContent = hours > 0 ? `${hours}시간 전` : "방금 전";

    const action = document.createElement("span");
    action.className = "card-action";
    action.textContent = "유튜브로 이동";

    meta.appendChild(time);
    meta.appendChild(action);
    info.appendChild(meta);

    card.appendChild(info);
    card.onclick = () => handleButtonClick(song.video_id);
    container.appendChild(card);
  });
}

function handleButtonClick(video_id) {
    window.location.href = `https://www.youtube.com/watch?v=${video_id}`;
}

document.addEventListener("DOMContentLoaded", fetchSongs);
document.addEventListener("DOMContentLoaded", attachReportForm);

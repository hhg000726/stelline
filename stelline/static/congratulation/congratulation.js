async function fetchSongs() {
    try {
        const response = await Stelline.api('congratulation/congratulations');
        const data = await response.json();
        data.sort((a, b) => new Date(b.counted_time) - new Date(a.counted_time));
        renderTable(data, "congratulationTable");
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
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
    const diff = Date.now() - new Date(song.counted_time).getTime() + 9 * 60 * 60 * 1000;
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
    button.innerHTML = '<svg data-feather="play" width="16" height="16"></svg> 유튜브로 이동';
    button.onclick = () => handleButtonClick(song.video_id);

    cta.appendChild(button);
    info.appendChild(cta);

    card.appendChild(info);
    container.appendChild(card);
  });

  if (window.feather) {
    feather.replace();
  }
}

function handleButtonClick(video_id) {
    window.location.href = `https://www.youtube.com/watch?v=${video_id}`;
}

document.addEventListener("DOMContentLoaded", fetchSongs);

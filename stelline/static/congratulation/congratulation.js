async function fetchSongs() {
    try {
        const response = await fetch('https://stelline.xyz/api/congratulation/congratulations');
        const data = await response.json();
        data.sort((a, b) => new Date(b.counted_time) - new Date(a.counted_time));
        renderTable(data, "congratulationTable");
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
}

function renderTable(data, tableId) {
  const tableBody = document.getElementById(tableId);
  tableBody.innerHTML = "";

  data.forEach(song => {
    const card = document.createElement("div");
    card.className = "card";

    const img = document.createElement("img");
    img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
    card.appendChild(img);

    const info = document.createElement("div");
    info.className = "info";

    const title = document.createElement("h3");
    title.textContent = `${Math.floor(song.count / 100000)}0만 달성!`;
    info.appendChild(title);

    const time = document.createElement("p");
    const diff = Date.now() - new Date(song.counted_time).getTime() + 9 * 60 * 60 * 1000;
    const hours = Math.floor(diff / 3600000);
    time.textContent = `${hours > 0 ? hours + '시간 전' : '방금 전'}`;
    info.appendChild(time);

    const button = document.createElement("button");
    button.textContent = "유튜브로 이동";
    button.onclick = () => handleButtonClick(song.video_id);
    info.appendChild(button);

    card.appendChild(info);
    tableBody.appendChild(card);
  });
}


function handleButtonClick(video_id) {
    // 클립보드 복사 + 유튜브 이동
    window.location.href = "https://www.youtube.com/watch?v=" + video_id;
}

document.addEventListener("DOMContentLoaded", fetchSongs);
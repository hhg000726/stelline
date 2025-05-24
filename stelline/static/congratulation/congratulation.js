async function fetchSongs() {
    try {
        const response = await fetch('https://stelline.site/api/congratulation/congratulations');
        const data = await response.json();
        data.sort((a, b) => new Date(b.counted_time) - new Date(a.counted_time));
        renderTable(data, "congratulationTable");
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
}

function renderTable(data, tableId) {
    const tableBody = document.getElementById(tableId);
    tableBody.innerHTML = ""; // 기존 데이터 제거
    
    data.forEach(song => {
        const row = document.createElement("tr");
        
        const thumbnailCell = document.createElement("td");
        const img = document.createElement("img");
        img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
        thumbnailCell.appendChild(img);
        row.appendChild(thumbnailCell);
        
        const queryCell = document.createElement("td");
        queryCell.textContent = Math.floor(song.count / 100000) + "0만 달성!";
        
        const button = document.createElement("button");
        button.textContent = "이동";
        button.onclick = () => handleButtonClick(song.query);
        queryCell.appendChild(button);
        row.appendChild(queryCell);

        const timeCell = document.createElement("td");
        const timeDifference = Date.now() - new Date(song.counted_time).getTime() + 9 * 60 * 60 * 1000;
        const seconds = Math.floor(timeDifference / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) {
            timeCell.textContent = `${days}일 전`;
        } else if (hours > 0) {
            timeCell.textContent = `${hours}시간 전`;
        } else if (minutes > 0) {
            timeCell.textContent = `${minutes}분 전`;
        } else {
            timeCell.textContent = `${seconds}초 전`;
        }
        row.appendChild(timeCell);
        
        tableBody.appendChild(row);
    });
}

function handleButtonClick(video_id) {
    // 클립보드 복사 + 유튜브 이동
    window.location.href = "https://www.youtube.com/watch?v=" + video_id;
}

document.addEventListener("DOMContentLoaded", fetchSongs);
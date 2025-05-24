async function fetchSongs() {
    try {
        const response = await fetch('https://stelline.site/api/congratulation/congratulations');
        const data = await response.json();
        populateTable(data);
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
}

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]]; // 배열 요소 스왑
    }
}

function populateTable(songs) {
    shuffleArray(songs);
    
    renderTable(songs, "songTable");
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
        queryCell.textContent = Math.floor(song.count / 100000) + "만 달성!";
        
        const button = document.createElement("button");
        button.textContent = "이동";
        button.onclick = () => handleButtonClick(song.query);
        queryCell.appendChild(button);
        row.appendChild(queryCell);
        
        tableBody.appendChild(row);
    });
}

function handleButtonClick(video_id) {
    // 클립보드 복사 + 유튜브 이동
    window.location.href = "https://www.youtube.com/watch?v=" + video_id;
}

document.addEventListener("DOMContentLoaded", fetchSongs);
fetchQueries();
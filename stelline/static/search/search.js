async function fetchSongs() {
    try {
        const response = await fetch('https://stelline.site/api/search/not_searched');
        const data = await response.json();
        if (typeof(data.searched_time) === "string") {
            document.getElementById("last-updated").innerText = data.searched_time
        }
        else {
            document.getElementById("last-updated").innerText = "마지막 검색 시도 시간: " + new Date(data.searched_time * 1000).toLocaleString()
        }
        populateTable(data.all_songs, data.recent);
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
}

async function fetchQueries() {
    try {
        // HTML 요소 가져오기
        const listElement = document.getElementById("query-list");

        const response = await fetch('https://stelline.site/api/search/sogns');
        const songs = await response.json();

        // JSON 데이터를 순회하면서 query 값만 추가
        songs.forEach(item => {
            const li = document.createElement("li");
            li.textContent = item.query;
            listElement.appendChild(li);
        });
    } catch (error) {
        console.error("JSON을 불러오는 중 오류 발생:", error);
        document.getElementById("json-time").textContent = "시간을 불러올 수 없습니다.";
    }
}

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]]; // 배열 요소 스왑
    }
}

function populateTable(songs, recent) {
    shuffleArray(songs);
    shuffleArray(recent);
    
    renderTable(songs, "songTable");
    renderTable(recent, "recentTable");
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
        queryCell.textContent = song.query;
        
        const button = document.createElement("button");
        button.textContent = "복사 & 이동";
        button.onclick = () => handleButtonClick(song.query);
        queryCell.appendChild(button);
        row.appendChild(queryCell);
        
        tableBody.appendChild(row);
    });
}

function handleButtonClick(query) {
    // API 요청
    fetch("https://stelline.site/api/search/record", {
        method: "GET",
        headers: { "Content-Type": "application/json" }
    }).catch(error => console.error("API 요청 중 오류 발생:", error));

    // 클립보드 복사 + 유튜브 이동
    navigator.clipboard.writeText(query).then(() => {
        window.location.href = "https://www.youtube.com/";
    });
}

document.addEventListener("DOMContentLoaded", fetchSongs);
fetchQueries();
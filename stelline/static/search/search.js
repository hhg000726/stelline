let allQueries = [];
let queryFilterBound = false;

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
        toggle.textContent = panel.hidden ? "검색어 추가 제안" : "제안 입력 닫기";
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
            const response = await Stelline.api("search/reports", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: value, captcha_token: captchaToken })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "제안을 보내지 못했습니다.");
            form.reset();
            status.textContent = result.message;
            window.turnstile?.reset(captchaWidget);
        } catch (error) {
            status.textContent = error.message;
            window.turnstile?.reset(captchaWidget);
        }
    });
}

async function fetchSongs() {
    try {
        const response = await Stelline.api('search/not_searched');
        const data = await response.json();
        if (data.searched_time === 0) {
            document.getElementById("last-updated").innerText = "마지막 검색 시도 시간: 없음"
        }
        else if (typeof(data.searched_time) === "string") {
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

function renderQueryList(filterText = "") {
    const listElement = document.getElementById("query-list");
    const countElement = document.getElementById("query-count");
    const normalizedFilter = filterText.trim().toLowerCase();

    const filteredQueries = allQueries.filter(item => {
        const query = String(item.query || "");
        return query.toLowerCase().includes(normalizedFilter);
    });

    listElement.innerHTML = "";

    if (filteredQueries.length === 0) {
        const emptyState = document.createElement("li");
        emptyState.className = "query-empty";
        emptyState.textContent = filterText.trim()
            ? "검색어를 찾을 수 없습니다."
            : "표시할 검색어가 없습니다.";
        listElement.appendChild(emptyState);
        countElement.textContent = "0개";
        return;
    }

    filteredQueries.forEach(item => {
        const li = document.createElement("li");
        li.className = "query-item";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "query-chip";
        button.textContent = item.query;
        button.title = item.query;
        button.onclick = () => handleButtonClick(item.query);

        li.appendChild(button);
        listElement.appendChild(li);
    });

    countElement.textContent = `${filteredQueries.length}개`;
}

function attachQueryFilter() {
    if (queryFilterBound) {
        return;
    }

    const input = document.getElementById("query-search");
    if (!input) {
        return;
    }

    input.addEventListener("input", (event) => {
        renderQueryList(event.target.value || "");
    });

    queryFilterBound = true;
}

async function fetchQueries() {
    try {
        const response = await Stelline.api('search/songs');
        const songs = await response.json();
        allQueries = Array.isArray(songs) ? songs : [];
        renderQueryList();
    } catch (error) {
        console.error("JSON을 불러오는 중 오류 발생:", error);
        const countElement = document.getElementById("query-count");
        if (countElement) {
            countElement.textContent = "불가";
        }
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

    renderCards(songs, "songCards");
    renderCards(recent, "recentCards");
}

function renderCards(data, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = ""; // 기존 제거

    data.forEach(song => {
        const card = document.createElement("div");
        card.className = "card";

        const img = document.createElement("img");
        img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
        card.appendChild(img);

        const info = document.createElement("div");
        info.className = "info";

        const title = document.createElement("h3");
        title.textContent = song.query;
        info.appendChild(title);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn-primary";
        button.innerHTML = '<svg data-feather="play" width="16" height="16"></svg> 복사 & 이동';
        button.onclick = () => handleButtonClick(song.query);
        info.appendChild(button);

        if (window.feather) {
            feather.replace();
        }

        card.appendChild(info);
        container.appendChild(card);
    });

    if (data.length === 0) {
        const message = document.createElement("h1");
        message.textContent = "검색 안되는 노래가 없습니다.";
        container.appendChild(message);
    }
}

function handleButtonClick(query) {
    // API 요청
    Stelline.api("search/record", {
        method: "GET",
        headers: { "Content-Type": "application/json" }
    }).catch(error => console.error("API 요청 중 오류 발생:", error));

    // 클립보드 복사 + 유튜브 이동
    navigator.clipboard.writeText(query).then(() => {
        window.location.href = "https://www.youtube.com/";
    });
}

document.addEventListener("DOMContentLoaded", fetchSongs);
document.addEventListener("DOMContentLoaded", attachReportForm);
fetchQueries();
attachQueryFilter();

let allQueries = [];
let queryFilterBound = false;

/* 같은 칸 안에서 목록을 바꿔 보여 주는 탭.
 * data-panel 값이 눌린 탭의 data-tab 과 같은 요소만 남긴다.
 *
 * role="tab" 을 붙여 둔 이상 탭처럼 움직여야 한다. 그래서 여기서
 * 탭과 칸을 aria 로 이어 주고, 좌우 화살표로도 옮겨 다닐 수 있게 한다.
 * (화살표가 없으면 화면 낭독기 사용자는 탭이라 안내받고도 넘길 수가 없다.) */
function attachTabs(groupId) {
    const group = document.getElementById(groupId);
    if (!group) return null;

    const buttons = Array.from(group.querySelectorAll("[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-panel]"))
        .filter(panel => buttons.some(button => button.dataset.tab === panel.dataset.panel));

    const panelFor = (name) => panels.find(panel => panel.dataset.panel === name);

    buttons.forEach((button, index) => {
        const panel = panelFor(button.dataset.tab);
        if (panel) {
            if (!button.id) button.id = `${groupId}-tab-${button.dataset.tab}`;
            if (!panel.id) panel.id = `${groupId}-panel-${button.dataset.tab}`;
            button.setAttribute("aria-controls", panel.id);
            panel.setAttribute("role", "tabpanel");
            panel.setAttribute("aria-labelledby", button.id);
        }
        // 탭 묶음은 통째로 한 번만 Tab 키에 걸린다. 그 안에서는 화살표로 옮긴다.
        button.tabIndex = button.classList.contains("is-on") ? 0 : -1;
        button.addEventListener("click", () => select(button));
        button.addEventListener("keydown", (event) => {
            const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
            if (!step) return;
            event.preventDefault();
            const next = buttons[(index + step + buttons.length) % buttons.length];
            select(next);
            next.focus();
        });
    });

    function select(button) {
        buttons.forEach(other => {
            const active = other === button;
            other.classList.toggle("is-on", active);
            other.setAttribute("aria-selected", String(active));
            other.tabIndex = active ? 0 : -1;
        });
        panels.forEach(panel => {
            panel.hidden = panel.dataset.panel !== button.dataset.tab;
        });
    }

    // 처음 열린 탭을 밖에서 정할 수 있게 고르는 함수를 돌려준다.
    return function selectByName(name) {
        const target = buttons.find(button => button.dataset.tab === name);
        if (target) select(target);
    };
}

/* 안내 그림은 PC와 모바일 두 벌이 있다. 휴대폰으로 들어온 사람에게 PC 화면부터
 * 보여 주면, 자기 화면과 다른 그림을 보고 한 번 더 눌러야 한다. */
function defaultMethodTab() {
    const coarsePointer = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    const narrow = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
    return coarsePointer || narrow ? "mobile" : "pc";
}

/* 안내 그림은 작게 늘어놓고, 누르면 원래 크기로 크게 본다. */
function attachImageViewer() {
    const viewer = document.getElementById("image-viewer");
    if (!viewer) return;
    const target = document.getElementById("image-viewer-target");
    const close = () => { viewer.hidden = true; };

    document.querySelectorAll(".step-media img").forEach(image => {
        image.tabIndex = 0;
        image.setAttribute("role", "button");
        const open = () => {
            target.src = image.src;
            target.alt = image.alt || "";
            viewer.hidden = false;
        };
        image.addEventListener("click", open);
        image.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                open();
            }
        });
    });

    viewer.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close();
    });
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

function setLastUpdated(searchedTime) {
    const node = document.getElementById("last-updated");
    if (!node) return;
    if (searchedTime === 0) {
        node.textContent = "마지막 검색 시도: 없음";
    } else if (typeof searchedTime === "string") {
        node.textContent = searchedTime;
    } else {
        node.textContent = "마지막 검색 시도: " + new Date(searchedTime * 1000).toLocaleString();
    }
}

async function fetchSongs() {
    try {
        const response = await Stelline.api('search/not_searched');
        const data = await response.json();
        setLastUpdated(data.searched_time);
        populateTable(data.all_songs, data.recent);
    } catch (error) {
        console.error('Error fetching songs:', error);
        ["songCards", "recentCards"].forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = '<p class="empty-state is-error">목록을 불러오지 못했습니다.</p>';
            }
        });
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

    // 검색어를 한 글자 칠 때마다 다시 그린다. 화면에 붙은 목록에 하나씩 넣으면
    // 항목 수만큼 배치가 다시 계산되므로, 조각에 모아 두었다가 한 번에 붙인다.
    const fragment = document.createDocumentFragment();
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
        fragment.appendChild(li);
    });
    listElement.appendChild(fragment);

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

function setTabCount(name, value) {
    const node = document.querySelector(`[data-count="${name}"]`);
    if (node) node.textContent = value;
}

function populateTable(songs, recent) {
    shuffleArray(songs);
    shuffleArray(recent);

    renderCards(songs, "songCards");
    renderCards(recent, "recentCards");
    setTabCount("current", songs.length);
    setTabCount("recent", recent.length);
}

function renderCards(data, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = ""; // 기존 제거

    // 카드를 하나씩 화면에 붙이지 않고 조각에 모아 한 번에 붙인다(배치 계산 1회).
    const fragment = document.createDocumentFragment();
    data.forEach(song => {
        // 카드 전체가 "복사 & 이동" 버튼이라 별도의 버튼 줄이 필요 없다.
        const card = document.createElement("button");
        card.type = "button";
        card.className = "card is-link";
        card.title = `${song.query} 복사하고 유튜브로 이동`;

        const thumb = document.createElement("div");
        thumb.className = "thumb-wrap";

        const img = document.createElement("img");
        img.src = `https://img.youtube.com/vi/${song.video_id}/0.jpg`;
        img.alt = "";
        img.loading = "lazy";
        thumb.appendChild(img);

        const play = document.createElement("span");
        play.className = "thumb-play";
        play.innerHTML = Stelline.icon("play");
        thumb.appendChild(play);
        card.appendChild(thumb);

        const info = document.createElement("div");
        info.className = "info";

        const title = document.createElement("h3");
        title.textContent = song.query;
        info.appendChild(title);

        const action = document.createElement("span");
        action.className = "card-action";
        action.textContent = "복사 & 이동";
        info.appendChild(action);

        card.appendChild(info);
        card.onclick = () => handleButtonClick(song.query);
        fragment.appendChild(card);
    });
    container.appendChild(fragment);

    if (data.length === 0) {
        const message = document.createElement("p");
        message.className = "empty-state";
        message.textContent = containerId === "recentCards"
            ? "최근 7일 이내에 막혔던 곡이 없습니다."
            : "검색 안되는 노래가 없습니다.";
        container.appendChild(message);
    }
}

async function handleButtonClick(query) {
    // API 요청
    Stelline.api("search/record", {
        method: "GET",
        headers: { "Content-Type": "application/json" }
    }).catch(error => console.error("API 요청 중 오류 발생:", error));

    // 예전에는 복사가 막히면 .then 이 실행되지 않아 눌러도 아무 일이 없었다.
    // 붙여 넣을 것이 없는 채로 유튜브에 보내 봐야 소용없으니, 그대로 두고 까닭을 알린다.
    if (!await Stelline.copyText(query)) {
        Stelline.toast("복사하지 못했어요. 검색어를 직접 선택해 복사해 주세요.");
        return;
    }
    // 복사에 성공하면 곧바로 유튜브로 넘어간다. 떠나는 길에 말풍선을 띄워 봐야
    // 한 번 깜빡이고 사라질 뿐이라, 여기서는 넘어가는 것 자체가 알림 역할을 한다.
    window.location.href = "https://www.youtube.com/";
}

document.addEventListener("DOMContentLoaded", fetchSongs);
document.addEventListener("DOMContentLoaded", attachReportForm);
document.addEventListener("DOMContentLoaded", () => {
    attachTabs("song-tabs");
    const selectMethodTab = attachTabs("method-tabs");
    if (selectMethodTab) selectMethodTab(defaultMethodTab());
    attachImageViewer();
});
fetchQueries();
attachQueryFilter();

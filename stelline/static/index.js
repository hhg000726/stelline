function toggleContent(id, button) {
  const content = document.getElementById(id);
  if (!content) return;

  const isHidden = content.hidden;
  content.hidden = !isHidden;
  button.classList.toggle("is-open", !isHidden);
  button.setAttribute("aria-expanded", String(!isHidden));
}

function copyText(id) {
  const textNode = document.getElementById(id);
  const text = textNode ? (textNode.dataset.copyText || textNode.innerText) : "";
  if (!text) {
    return;
  }

  Stelline.api("main/record", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  }).catch(error => console.error("API 요청 중 오류 발생:", error));

  navigator.clipboard.writeText(text).then(() => {
    window.open("https://x.com/", "_blank", "noopener,noreferrer");
  }).catch(err => {
    console.error("복사 실패: ", err);
  });
}

function showEmptyState(container, message, isError = false) {
  if (!container) return;
  container.innerHTML = "";
  const note = document.createElement("p");
  note.className = isError ? "empty-state is-error" : "empty-state";
  note.textContent = message;
  container.appendChild(note);
}

function toArray(value) {
  if (value == null) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "object") return Object.values(value);
  return [value];
}

async function fetchBugs() {
  try {
    const response = await Stelline.api("bugs/rank");
    const recentData = await response.json();
    const bugsDiv = document.getElementById("bugs");
    const panel = bugsDiv.closest(".section-panel");
    const bugEntries = toArray(recentData).filter(Boolean);

    if (!bugEntries.length) {
      if (panel) panel.style.display = "none";
      return;
    }

    bugsDiv.innerHTML = "";

    bugEntries.forEach((entry, index) => {
      const name = entry.name || Object.keys(recentData || {})[index] || `대상${index + 1}`;
      const data = entry || {};
      const title = data.title || "";
      const diffs = data.diffs || {};
      const urlNumber = data.url_number || "";
      const contentId = `hiddenContent_bug_${name.replace(/\s+/g, "_")}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "toggle-button btn-secondary";
      // 순위는 펼치지 않아도 보이는 편이 훨씬 쓸모 있다.
      button.innerHTML = `<span>벅스 ${Stelline.escapeHtml(name)}${title ? ` · ${Stelline.escapeHtml(title)}` : ""}</span>`
        + (data.rank ? `<span class="toggle-meta">현재 ${Number(data.rank)}위</span>` : "");
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", () => toggleContent(contentId, button));

      const content = document.createElement("div");
      content.id = contentId;
      content.className = "list-item-content";
      content.hidden = true;
      content.innerHTML = `
        <div class="list-item-body">
          <strong>현재 ${data.rank || 0}위</strong>
          <p>${data.rank === 2 ? `1등과의 차이: ${diffs.count_to_first ?? 0}표${diffs.streaming_to_first ? ` / ${diffs.streaming_to_first}%` : ""}` : ""}</p>
          <p>${data.rank === 3 ? `2등과의 차이: ${diffs.count_to_second ?? 0}표${diffs.streaming_to_second ? ` / ${diffs.streaming_to_second}%` : ""}` : ""}</p>
          <p>${data.rank > 2 ? `윗등수와의 차이: ${diffs.count_diff ?? 0}표${diffs.streaming_diff ? ` / ${diffs.streaming_diff}%` : ""}` : ""}</p>
          <p>매일 계정마다 하트 100개를 무료로 줍니다</p>
          <p>계정은 같은 번호로 3개까지 만들 수 있습니다</p>
          <p>광고를 시청하여 하트를 얻을 수도 있습니다</p>
          <button type="button" class="btn-secondary" onclick="window.location.href='https://favorite.bugs.co.kr/${urlNumber}'">벅스 바로가기</button>
        </div>
      `;

      bugsDiv.appendChild(button);
      bugsDiv.appendChild(content);
    });
  } catch (error) {
    console.error("벅스 데이터 로드 실패:", error);
    showEmptyState(document.getElementById("bugs"), "벅스 순위를 불러오지 못했습니다.", true);
  }
}

async function fetchEvents() {
  const container = document.getElementById("button-container");
  const panel = container.closest(".section-panel");

  try {
    const res = await Stelline.api("main/events", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });
    const events = toArray(await res.json());

    if (!events.length) {
      if (panel) panel.style.display = "none";
      return;
    }

    container.innerHTML = "";
    events.forEach(event => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn-secondary";
      button.textContent = event.title || "이벤트";
      button.onclick = () => {
        if (event.link) {
          window.location.href = event.link;
        }
      };
      container.appendChild(button);
    });
  } catch (error) {
    console.error("이벤트 API 요청 중 오류 발생:", error);
    showEmptyState(container, "이벤트 정보를 불러오지 못했습니다.", true);
  }
}

async function fetchTwits() {
  try {
    const res = await Stelline.api("main/twits");
    const data = toArray(await res.json());
    const container = document.getElementById("twitContainer");
    const panel = container.closest(".section-panel");

    if (!data.length) {
      if (panel) panel.style.display = "none";
      return;
    }

    container.innerHTML = "";

    data.forEach((item, idx) => {
      const btnId = `hiddenContent_twit_${idx}`;
      const keywords = String(item.keywords || "").split(",").map(keyword => keyword.trim()).filter(Boolean);
      const tags = String(item.tags || "").split(",").map(tag => tag.trim()).filter(Boolean);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "toggle-button btn-secondary";
      // 총공 시간은 펼치기 전에도 보여야 "언제 하는지"를 바로 알 수 있다.
      const time = String(item.time || "").trim();
      button.innerHTML = `<span>${Stelline.escapeHtml(item.title || `트윗 안내 ${idx + 1}`)}</span>`
        + `<span class="toggle-meta">${Stelline.escapeHtml(time || "임시 연기")}</span>`;
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", () => toggleContent(btnId, button));

      const content = document.createElement("div");
      content.id = btnId;
      content.className = "list-item-content";
      content.hidden = true;

      const descHTML = `
        <div class="list-item-body">
          <p>태그와 키워드를 사용하여 트윗 작성</p>
          <p>태그 검색 후 다른 트윗 리트윗 & 좋아요 누르기</p>
          <p>시간상 참여가 어려우신 분들은 예약 트윗을 활용해주세요.<br>같은 내용의 트윗은 중복 작성되지 않습니다.<br>하고 싶은 말 부분을 필수로 작성해주시기 바랍니다.</p>
          <h3>태그 & 키워드</h3>
        </div>
      `;
      content.innerHTML = descHTML;

      const wrapper = document.createElement("div");
      wrapper.className = "copy-grid";

      keywords.forEach((keyword, keywordIndex) => {
        const copyId = `copyText${idx}_${keywordIndex}`;
        const copyTextValue = [keyword, ...tags.map(tag => `#${tag}`)].join("\n");
        const copyContainer = document.createElement("div");
        copyContainer.className = "copy-card";
        copyContainer.innerHTML = `
          <div class="copy-card-top">
            <div class="copy-card-kicker">키워드</div>
          </div>
          <p class="copy-text" id="${copyId}" data-copy-text="${Stelline.escapeHtml(copyTextValue)}">
            <strong>${Stelline.escapeHtml(keyword)}</strong>
          </p>
          <div class="tag-list">
            ${tags.map(tag => `<span class="tag-chip">#${Stelline.escapeHtml(tag)}</span>`).join("")}
          </div>
          <button type="button" class="btn-primary copy-button" data-id="${copyId}">복사 & 이동</button>
        `;
        wrapper.appendChild(copyContainer);
      });

      content.appendChild(wrapper);
      container.appendChild(button);
      container.appendChild(content);
    });

    document.querySelectorAll(".copy-button").forEach(button => {
      button.addEventListener("click", function () {
        copyText(this.getAttribute("data-id"));
      });
    });
  } catch (err) {
    console.error("트윗 데이터 로드 실패:", err);
    showEmptyState(document.getElementById("twitContainer"), "트윗 안내를 불러오지 못했습니다.", true);
  }
}

const BUTTON_CACHE_KEY = "stelline.main.buttons";

function applyButtonConfig(buttons) {
  const container = document.getElementById("main-nav");
  if (!container || !Array.isArray(buttons) || !buttons.length) return;

  const nodes = new Map();
  container.querySelectorAll("[data-button-key]").forEach(node => nodes.set(node.dataset.buttonKey, node));

  buttons
    .slice()
    .sort((a, b) => (a.order || 0) - (b.order || 0))
    .forEach(config => {
      // DB에 없는 버튼은 손대지 않는다. 화면에 새 버튼을 먼저 넣어도 사라지지 않는다.
      const node = nodes.get(config.key);
      if (!node) return;
      node.hidden = !config.visible;
      const labelNode = node.querySelector("[data-button-label]");
      if (labelNode && config.label) labelNode.textContent = config.label;
      container.appendChild(node);
    });
}

async function fetchMainButtons() {
  // 지난번 설정을 먼저 반영해, 숨긴 버튼이 잠깐 보였다 사라지지 않게 한다.
  try {
    const cached = window.localStorage.getItem(BUTTON_CACHE_KEY);
    if (cached) applyButtonConfig(JSON.parse(cached));
  } catch (error) {
    /* 저장소를 못 쓰는 환경에서는 그냥 넘어간다. */
  }

  try {
    const res = await Stelline.api("main/buttons");
    const buttons = toArray(await res.json());
    applyButtonConfig(buttons);
    // 조회 실패 시 빈 목록이 오는데, 이걸 저장하면 다음 방문에서 숨긴 버튼이 잠깐 보인다.
    if (buttons.length) {
      try {
        window.localStorage.setItem(BUTTON_CACHE_KEY, JSON.stringify(buttons));
      } catch (error) {
        /* 저장 실패는 무시한다. */
      }
    }
  } catch (error) {
    // 설정을 못 받아오면 HTML에 적힌 기본 상태(전부 표시)를 그대로 둔다.
    console.error("메인 버튼 설정 로드 실패:", error);
  }
}

fetchMainButtons();
fetchTwits();
fetchEvents();
fetchBugs();

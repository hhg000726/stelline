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
      button.textContent = `벅스 ${name}${title ? ` · ${title}` : ""}`;
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
      button.textContent = item.title || `트윗 안내 ${idx + 1}`;
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
          <p>${item.time && item.time.trim() ? item.time : "임시 연기"}</p>
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
  }
}

fetchTwits();
fetchEvents();
fetchBugs();

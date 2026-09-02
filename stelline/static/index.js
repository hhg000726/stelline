function toggleContent(id, button) {
  const content = document.getElementById(id);
  if (!content) return;

  const isHidden = content.hidden;
  content.hidden = !isHidden;
  button.classList.toggle("is-open", !isHidden);
  button.setAttribute("aria-expanded", String(!isHidden));
}

async function copyText(id) {
  const textNode = document.getElementById(id);
  const text = textNode ? (textNode.dataset.copyText || textNode.innerText) : "";
  if (!text) {
    return;
  }

  Stelline.api("main/record", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  }).catch(error => console.error("API 요청 중 오류 발생:", error));

  // 복사에 실패하면 X로 보내 봐야 붙여 넣을 것이 없다. 그대로 두고 까닭을 알린다.
  if (!await Stelline.copyText(text)) {
    Stelline.toast("복사하지 못했어요. 키워드를 직접 선택해 복사해 주세요.");
    return;
  }

  // 새 창 열기가 막히면(팝업 차단) 아무 일도 없는 것처럼 보인다. 그때는 이 창에서 넘어간다.
  // 넘어가는 쪽은 화면이 통째로 바뀌니 그 자체가 알림이고, 말풍선은 깜빡이기만 한다.
  const opened = window.open("https://x.com/", "_blank", "noopener,noreferrer");
  if (opened) {
    Stelline.toast("복사했어요. 새 탭에서 X를 열었습니다.");
  } else {
    window.location.href = "https://x.com/";
  }
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

/* 윗등수와의 차이 한 줄.
 *
 * 예전에는 순위별로 <p>를 세 개 깔아 두고 해당하지 않는 둘은 빈 칸으로 남겼다.
 * 순위마다 할 말은 하나뿐이라, 그 하나만 돌려준다. */
function rankGapText(rank, diffs = {}) {
  const votes = (count) => `${count ?? 0}표`;
  const share = (percent) => (percent ? ` / ${percent}%` : "");
  if (rank === 2) return `1등과의 차이: ${votes(diffs.count_to_first)}${share(diffs.streaming_to_first)}`;
  if (rank === 3) return `2등과의 차이: ${votes(diffs.count_to_second)}${share(diffs.streaming_to_second)}`;
  if (rank > 3) return `윗등수와의 차이: ${votes(diffs.count_diff)}${share(diffs.streaming_diff)}`;
  return "";
}

async function fetchBugs() {
  try {
    const response = await Stelline.api("bugs/rank");
    const recentData = await response.json();
    const bugsDiv = document.getElementById("bugs");
    const panel = bugsDiv.closest(".section-panel");
    const bugEntries = toArray(recentData).filter(Boolean);

    if (!bugEntries.length) {
      if (panel) panel.hidden = true;
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
      // 순위마다 해당하는 줄이 하나뿐이라, 나머지를 빈 <p>로 남기지 않고 아예 만들지 않는다.
      const gap = rankGapText(data.rank, diffs);
      content.innerHTML = `
        <div class="list-item-body">
          <strong>현재 ${Number(data.rank) || 0}위</strong>
          ${gap ? `<p>${Stelline.escapeHtml(gap)}</p>` : ""}
          <p>매일 계정마다 하트 100개를 무료로 줍니다</p>
          <p>계정은 같은 번호로 3개까지 만들 수 있습니다</p>
          <p>광고를 시청하여 하트를 얻을 수도 있습니다</p>
          <a class="btn-secondary" href="https://favorite.bugs.co.kr/${encodeURIComponent(urlNumber)}" target="_blank" rel="noopener noreferrer">벅스 바로가기</a>
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
      if (panel) panel.hidden = true;
      return;
    }

    container.innerHTML = "";
    // 바깥 사이트로 나가는 자리는 버튼이 아니라 링크로 둔다. 그래야 새 탭으로 열거나
    // 주소를 미리 보는, 링크라면 당연히 되는 일들이 그대로 된다.
    events.forEach(event => {
      const link = document.createElement("a");
      link.className = "btn-secondary";
      link.textContent = event.title || "이벤트";
      // href 가 없는 <a> 는 눌리지도 초점이 가지도 않는다. 주소가 빠진 이벤트가
      // 눌리는 것처럼 보였다가 아무 일도 안 하는 것보다 낫다.
      if (event.link) {
        link.href = event.link;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      container.appendChild(link);
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
      if (panel) panel.hidden = true;
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

fetchTwits();
fetchEvents();
fetchBugs();

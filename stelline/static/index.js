function toggleContent(id, button) {
  let content = document.getElementById(id);
  if (content.style.display === "none" || content.style.display === "") {
    content.style.display = "block";
  } else {
    content.style.display = "none";
  }
}

function copyText(id) {
  let text = document.getElementById(id).innerText;
  fetch("https://stelline.site/api/main/record", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
  }).catch(error => console.error("API 요청 중 오류 발생:", error));
  navigator.clipboard.writeText(text).then(() => {
    window.location.href = "https://www.x.com/";
  }).catch(err => {
    console.error("복사 실패: ", err);
  });
}

async function fetchBugs() {
  try {
      const response = await fetch('https://stelline.site/api/bugs/rank');
      const recentData = await response.json();
      const bugsDiv = document.getElementById("bugs");

      for (const name in recentData) {
          const data = recentData[name];
          const title = data.title
          const diffs = data.diffs;
          const url_number = data.url_number
          const contentId = "hiddenContent_" + name.replace(/\s+/g, "_");
          let displayHtml = `<button class="toggle-button" data-name="${name}" onclick="toggleContent('${contentId}', this)">벅스 ${name} ${title}</button>`;
          displayHtml += `<div class="content" id="${contentId}">`;
          displayHtml += `<h2>현재 ${data.rank}위</h2><p>`;
          
          if (data.rank === 2) {
              displayHtml += `1등과의 차이: ${diffs.count_to_first}표${diffs.streaming_to_first ? ` / ${diffs.streaming_to_first}%` : ''}<br>`;
              displayHtml += ` (${data.message} 남았습니다)<br>`;
          } else if (data.rank === 3) {
              displayHtml += `1등과의 차이: ${diffs.count_to_first}표${diffs.streaming_to_first ? ` / ${diffs.streaming_to_first}%` : ''}<br>`;
              displayHtml += `2등과의 차이: ${diffs.count_to_second}표${diffs.streaming_to_second ? ` / ${diffs.streaming_to_second}%` : ''}<br>`;
          } else if (data.rank > 1) {
              displayHtml += `1등과의 차이: ${diffs.count_to_first}표${diffs.streaming_to_first ? ` / ${diffs.streaming_to_first}%` : ''}<br>`;
              displayHtml += `2등과의 차이: ${diffs.count_to_second}표${diffs.streaming_to_second ? ` / ${diffs.streaming_to_second}%` : ''}<br>`;
              displayHtml += `윗등수와의 차이: ${diffs.count_diff}표${diffs.streaming_diff ? ` / ${diffs.streaming_diff}%` : ''}<br>`;
          }
          displayHtml += `<p>매일 계정마다 하트 100개를 무료로 줍니다</p>`;
          displayHtml += `<p>계정은 같은 번호로 3개까지 만들 수 있습니다</p>`;
          displayHtml += `<p>광고를 시청하여 하트를 얻을 수도 있습니다</p>`;
          displayHtml += `<button onclick="window.location.href='https://favorite.bugs.co.kr/${url_number}'">벅스 바로가기</button>`
          displayHtml += `</div>`;
          bugsDiv.innerHTML += displayHtml;
      }
      
  } catch (error) {
      console.error('Error fetching songs:', error);
  }
}

async function fetchEvents() {
  const container = document.getElementById("button-container");

  try {
    const res = await fetch("https://stelline.site/api/main/events", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });

    const events = await res.json();  // 응답을 JSON으로 파싱

    events.forEach(event => {
      const button = document.createElement("button");
      button.textContent = event.title;
      button.onclick = () => window.location.href = event.link;
      container.appendChild(button);
    });
  } catch (error) {
    console.error("API 요청 중 오류 발생:", error);
  }
}

async function fetchTwits() {
  try {
    const res = await fetch("https://stelline.site/api/main/twits");
    const data = await res.json();

    const container = document.getElementById("twitContainer");

    data.forEach((item, idx) => {
      const btnId = `hiddenContent${idx}`;
      const copyIds = item.keywords.split(',').map(keyword => keyword.trim()).map((_, i) => `copyText${idx}_${i}`);

      const button = document.createElement("button");
      button.className = "toggle-button";

      const timeText = item.time.trim() ? item.time : "임시 연기";
      button.innerText = `${item.title}`;
      button.setAttribute("onclick", `toggleContent('${btnId}', this)`);

      const content = document.createElement("div");
      content.className = "content";
      content.id = btnId;

      const descHTML = `
        <p>태그와 키워드를 사용하여 트윗 작성</p>
        <p>태그 검색후 다른 트윗 리트윗 & 좋아요 누르기</p>
        <p>${timeText}</p>
        <p>시간상 참여가 어려우신 분들은 예약 트윗을 활용해주세요<br>
        예약 트윗을 작성할 때, 같은 내용의 트윗은 작성 되지 않습니다<br>
        하고 싶은 말 부분을 필수로 작성해주시기 바랍니다</p>
        <h2>태그 & 키워드</h2>
      `;
      content.innerHTML = descHTML;

      const wrapper = document.createElement("div");
      wrapper.className = "wrapper";

      item.keywords.split(',').map(keyword => keyword.trim()).forEach((keyword, i) => {
        const copyContainer = document.createElement("div");
        copyContainer.className = "copy-container";

        const tagLines =  item.tags.split(',').map(tag => tag.trim()).map(tag => `<span>#${tag}</span>`).join("<br>");
        const tagText = `
          <p class="copy-text" id="${copyIds[i]}">
            <span>${keyword}</span><br>
            ${tagLines}
          </p>
          <button class="copy-button" data-id="${copyIds[i]}">복사<br>이동</button>
        `;
        copyContainer.innerHTML = tagText;
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
fetchEvents()
fetchBugs()
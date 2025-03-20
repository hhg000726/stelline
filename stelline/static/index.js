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
  navigator.clipboard.writeText(text).then(() => {
    window.location.href = "https://www.x.com/";
  }).catch(err => {
    console.error("복사 실패: ", err);
  });
}

document.querySelectorAll(".copy-button").forEach(button => {
  button.addEventListener("click", function () {
    copyText(this.getAttribute("data-id"));
  });
});

async function fetchSongs() {
  try {
      const response = await fetch('https://stelline.site/api/bugs/rank');
      const recentData = await response.json();
      const rankingsDiv = document.getElementById("rankings");

      for (const name in recentData) {
          const data = recentData[name];
          const title = data.title
          const diffs = data.diffs;
          const url_number = data.url_number
          const contentId = "hiddenContent_" + name.replace(/\s+/g, "_");
          let displayHtml = `<button class="toggle-button" data-name="${name}" onclick="toggleContent('${contentId}', this)">벅스 ${name} ${title}</button>`;
          displayHtml += `<div class="content" id="${contentId}">`;
          displayHtml += `<h2>${data.rank}위</h2><p>`;
          
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
          rankingsDiv.innerHTML += displayHtml;
      }
  } catch (error) {
      console.error('Error fetching songs:', error);
  }
}

fetchSongs()
let username = "";
let currentGame = {};

function startGame() {
  fetch("https://stelline.site/api/newone/start_game", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  })
    .then(response => response.json())
    .then(data => {
      username = data.username;
      document.getElementById("start-btn").style.display = "none";
      document.getElementById("leaderboard").style.display = "none";
      currentGame = data;
      nextRound();
    })
    .catch((error) => {
      alert(`오류 발생: ${error.message}`);
      console.log(error);
    });
}

function nextRound() {
  let left = currentGame.left;
  let right = currentGame.right;
  document.getElementById("game").style.display = "flex";
  document.getElementById("score").style.display = "block";
  document.getElementById("score").innerText = "점수: " + currentGame.score;
  document.getElementById("left-title").innerText = left.title;
  document.getElementById("left-thumbnail").src = `https://img.youtube.com/vi/${left.video_id}/0.jpg`;
  document.getElementById("left-link").href = `https://www.youtube.com/watch?v=${left.video_id}`;
  document.getElementById("right-title").innerText = right.title;
  document.getElementById("right-thumbnail").src = `https://img.youtube.com/vi/${right.video_id}/0.jpg`;
  document.getElementById("right-link").href = `https://www.youtube.com/watch?v=${right.video_id}`;
}

function guess(choice) {
  fetch("https://stelline.site/api/newone/submit_choice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username, choice: choice })
  })
    .then(response => response.json())
    .then(data => {
      if (data.message === "정답!") {
        currentGame = data;
        nextRound();
      }
      else {
        if (data.message === "끝!") {
          alert(`${data.message}\n코드: ${data.username}\n점수: ${data.score}\n시간: ${data.elapsed_time}`);
        }
        else {
          alert(`${data.message}\n점수: ${data.score}\n시간: ${data.elapsed_time}`);
        }
        document.getElementById("start-btn").style.display = "inline-block";
        document.getElementById("game").style.display = "none";
        document.getElementById("score").style.display = "none";
        username = "";
        document.getElementById("leaderboard").style.display = "block";
        loadLeaderboard();
      }
    })
    .catch((error) => {
      alert(`오류 발생: ${error.message}`);
      console.log(error);
    });;
}

function loadLeaderboard() {
  fetch("https://stelline.site/api/newone/leaderboard")
    .then(response => response.json())
    .then(data => {
      let rows = data.map((entry, index) =>
        `<tr><td>${index + 1}</td><td>${entry.username}</td><td>${entry.score}</td><td>${entry.time}</td></tr>`
      ).join("");

      document.getElementById("leaderboard").innerHTML = `
        <h2>🏆 리더보드</h2>
        <table>
          <tr><th>순위</th><th>코드</th><th>점수</th><th>시간</th></tr>
          ${rows}
        </table>
      `;
      document.getElementById("leaderboard").style.display = "block";
    })
    .catch((error) => {
      alert(`오류 발생: ${error.message}`);
      console.log(error);
    });
}

window.onload = () => {
  loadLeaderboard();
};
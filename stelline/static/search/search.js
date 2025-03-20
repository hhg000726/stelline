const queries = [
    "스텔라이브 starry way",
    "스텔라이브 milky way",
    "스텔라이브 stars align",
    "스텔라이브 our tales",
    "스텔라이브 소리가나는쪽으로",
    "칸나 어딕션",
    "칸나 푸른보석과어린용",
    "칸나 색채",
    "칸나 최종화",
    "칸나 frozen eclipse",
    "칸나 요미 공주열차",
    "칸나 요미 8.32",
    "칸나 love wins all",
    "칸나 역광",
    "칸나 애타는한가슴을달랠수있다면",
    "칸나 최종화 어쿠스틱",
    "칸나 괴수의꽃노래",
    "칸나 감그레이",
    "칸나 사랑해줘",
    "칸나 지구본",
    "칸나 킥백",
    "칸나 레이디",
    "칸나 잠이드는거리",
    "칸나 아이돌",
    "칸나 에러",
    "칸나 스즈메",
    "칸나 삼문소설",
    "칸나 신시대",
    "칸나 좋아하니까",
    "칸나 나는최강",
    "유니 내꺼하는법",
    "유니 supadopa",
    "유니 마시로 해피신디사이저",
    "유니 칸나 점묘의노래",
    "유니 superpower",
    "유니 두근어질",
    "유니 멜라",
    "유니 아이돌",
    "유니 굿바이선언",
    "유니 사랑의말",
    "유니 베텔기우스",
    "유니 긍지높은아이돌",
    "히나 하나",
    "히나 낙향",
    "히나 피날레",
    "히나 달을가",
    "히나 하루카",
    "히나 새벽과반딧불이",
    "히나 17살의노래",
    "히나 봄을기다리다",
    "히나 라푼젤",
    "히나 sweet dreams my dear",
    "히나 드라마",
    "히나 그저네게맑아라",
    "스텔라이브 앨뮤랜",
    "히나 만찬가",
    "마시로 봄꿈",
    "히나 마시로 dear my fairy",
    "마시로 퀘스천",
    "마시로 pale",
    "마시로 우주비행사의노래",
    "마시로 츄다양성",
    "마시로 안녕꽃도둑씨",
    "마시로 댄스로봇댄스",
    "마시로 연예인",
    "리제 festa",
    "힛온샷",
    "리제 벚꽃너나",
    "리제 내일의밤하늘초계반",
    "리제 린 아파트",
    "리제 제이팝매쉬업",
    "리제 끝나지않은노래",
    "리제 비바라비다",
    "리제 밀월",
    "리제 드라우닝",
    "리제 프라이드혁명",
    "리제 멜트",
    "리제 괴수의꽃노래",
    "리제 절정찬가",
    "리제 눈이녹을때",
    "리제 Stranger",
    "리제 나라는것",
    "리제 괴물",
    "리제 선잠",
    "타비 그여름의어느날은",
    "타비 그여름에피어나",
    "타비 낮에뜨는달",
    "타비 첫사랑",
    "타비 hero",
    "타비 be somebody",
    "타비 사신",
    "타비 마시로 안녕또언젠가",
    "타비 여로",
    "시부키 겨울의선물",
    "시부키 sabotage",
    "시부키 레오",
    "시부키 여우비",
    "시부키 너에게메롱",
    "린 나나 역몽",
    "린 시부키 아이덴티티",
    "린 복숭아색열쇠",
    "린 wxy",
    "린 to x",
    "린 꿈의카니발",
    "린 specialz",
    "린 해피엔드",
    "린 overdose",
    "린 사랑감기에실려",
    "린 무희",
    "린 루머",
    "린 안녕또언젠가",
    "린 유령도쿄",
    "나나 리코 린 beyond the way",
    "나나 비행정",
    "나나 born to run",
    "나나 실부프레지던트",
    "나나 신같네",
    "나나 사무라이하트",
    "나나 푸른산호초",
    "나나 가짜얼굴",
    "리코 래빗홀",
    "리코 마음예보",
    "리코 시부키 절대적완전싫어",
    "리코 꽃의탑",
    "리코 크리스마스송",
    "리코 주름맞추기",
    "리코 경화수월",
    "리코 케세라세라",
    "리코 톤데모원더즈",
    "리코 린 getcha",
    "리코 맑은날",
    "리코 지구를줄게",
    "리코 괴수의꽃노래",
    "리코 용사",
    "리코 모니터링"
];

async function fetchSongs() {
    try {
        const response = await fetch('https://stelline.site/api/search/not_searched'); // 실제 API 엔드포인트로 변경 필요
        const data = await response.json();
        const recentArray = Object.entries(data.recent).map(([query, values]) => ({
            query: query,
            video_id: values[0], // 첫 번째 값이 video_id
            timestamp: values[1]  // 두 번째 값이 timestamp
        }));
        if (typeof(data.searched_time) === "string") {
            document.getElementById("last-updated").innerText = data.searched_time
        }
        else {
            document.getElementById("last-updated").innerText = "마지막으로 검색된 시간: " + new Date(data.searched_time * 1000).toLocaleString()
        }
        populateTable(data.all_songs, recentArray);
    } catch (error) {
        console.error('Error fetching songs:', error);
    }
}

async function fetchQueries() {
    try {
        // HTML 요소 가져오기
        const listElement = document.getElementById("query-list");
        
        // JSON 데이터를 순회하면서 query 값만 추가
        queries.forEach(item => {
            const li = document.createElement("li");
            li.textContent = item;
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
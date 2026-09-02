/* 오프라인 이벤트 화면.
 *
 * 지도만 두면 표시된 행사가 몇 개인지 알 수 없고, 마커를 하나씩 눌러야만 내용을 볼 수 있다.
 * 같은 데이터를 목록으로도 보여 주고, 목록과 지도를 서로 연결한다.
 */
const today = new Date();
let openInfoWindow = null;
let allEvents = [];
let map = null;
let entries = [];
/* 지금 화면에 그려 둔 행사들. 지도 인증 실패처럼 나중에 알려지는 일이 생기면
 * 같은 목록을 다시 그려야 해서 들고 있는다. */
let currentEvents = [];

function formatDate(dateStr) {
  const date = new Date(dateStr);
  const year = date.getUTCFullYear();
  if (year >= 3000) return "(미정)";
  return `${year}.${date.getUTCMonth() + 1}.${date.getUTCDate()}`;
}

function formatDateRange(startStr, endStr) {
  const start = new Date(startStr);
  const end = new Date(endStr);

  if (start.getFullYear() >= 3000 && end.getFullYear() >= 3000) return "(미정)";

  const startFormatted = formatDate(startStr);
  const endFormatted = formatDate(endStr);

  return startFormatted === endFormatted
    ? startFormatted
    : `${startFormatted} ~ ${endFormatted}`;
}

function eventLinks(event) {
  return String(event.description || "")
    .split(",")
    .map(link => link.trim())
    .filter(Boolean);
}

/* 지도를 못 띄웠을 때. 예전에는 지도 자리가 아무 설명 없는 빈 상자로 남아,
 * 아직 불러오는 중인지 고장인지 알 수 없었다. 목록은 그대로 쓸 수 있으므로 그쪽으로 안내한다. */
function showMapUnavailable() {
  const shell = document.getElementById('map');
  if (!shell) return;
  map = null;
  shell.classList.add('is-unavailable');
  // 지도 쪽에서 뒤늦게 제 오류 화면을 그려 넣기도 한다. 우리 안내만 남도록
  // 이 칸의 다른 자식은 CSS에서 감춘다(아래 .map-shell.is-unavailable 규칙).
  if (shell.querySelector('.map-fallback')) return;
  const note = document.createElement('p');
  note.className = 'map-fallback';
  note.textContent = '지도를 불러오지 못했습니다. 아래 목록에서 장소와 기간을 확인해 주세요.';
  shell.appendChild(note);
}

/* 지도 인증이 막히면(키 만료·사용량 초과 등) 스크립트는 멀쩡히 올라오고 화면만 비어
 * 있다. 이 이름의 함수를 지도 쪽에서 직접 불러 주므로, 그때도 같은 안내를 보여 준다. */
window.navermap_authFailure = function () {
  showMapUnavailable();
  renderList(currentEvents);
};

function initMap() {
  if (!window.naver || !window.naver.maps) {
    showMapUnavailable();
    return;
  }
  map = new naver.maps.Map('map', {
    center: new naver.maps.LatLng(36.5, 127.5),
    zoom: 7
  });
}

function clearMarkers() {
  entries.forEach(entry => entry.marker.setMap(null));
  entries = [];
  openInfoWindow?.close();
  openInfoWindow = null;
}

/* 목록에서 고른 행사를 지도에서도 펼쳐 보여 준다. */
function focusEvent(index) {
  const entry = entries[index];
  if (!entry || !map) return;

  const cards = document.querySelectorAll('.event-card');
  cards.forEach((card, cardIndex) => {
    card.classList.toggle('is-on', cardIndex === index);
  });
  // 지도의 마커에서 들어온 경우, 짝이 되는 카드가 목록 밖으로 밀려 있을 수 있다.
  cards[index]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

  map.setCenter(entry.marker.getPosition());
  map.setZoom(Math.max(map.getZoom(), 13));
  openInfoWindow?.close();
  entry.infowindow.open(map, entry.marker);
  openInfoWindow = entry.infowindow;
}

function renderList(events) {
  const list = document.getElementById('event-list');
  const count = document.getElementById('event-count');
  if (!list) return;

  currentEvents = events;
  list.innerHTML = "";
  if (count) count.textContent = `${events.length}건`;

  if (!events.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = '진행 중인 오프라인 이벤트가 없습니다.';
    list.appendChild(empty);
    return;
  }

  // 카드를 목록에 하나씩 붙이면 그때마다 배치가 다시 계산된다. 조각에 모아 한 번에 붙인다.
  const fragment = document.createDocumentFragment();
  events.forEach((event, index) => {
    // 예전에는 카드 자체가 <button>이고 관련 링크가 그 안에 들어 있었다. 버튼 안의
    // 링크는 표준에서 허용하지 않고 화면 낭독기도 제대로 읽지 못한다. 그래서 지도로
    // 옮기는 부분만 버튼으로 두고, 링크는 그 옆(버튼 바깥)에 나란히 둔다.
    const card = document.createElement('div');
    card.className = 'event-card';

    // 지도를 못 불러왔다면 눌러도 옮겨 갈 곳이 없다. 그때는 눌리지 않는 칸으로 둔다.
    const focusButton = document.createElement(map ? 'button' : 'div');
    if (map) focusButton.type = 'button';
    focusButton.className = 'event-card-main';

    const name = document.createElement('strong');
    name.textContent = event.name || '오프라인 이벤트';
    focusButton.appendChild(name);

    const place = document.createElement('span');
    place.className = 'event-place';
    place.textContent = event.location_name || event.address || '';
    focusButton.appendChild(place);

    const date = document.createElement('span');
    date.className = 'event-date';
    date.textContent = formatDateRange(event.start_date, event.end_date);
    focusButton.appendChild(date);

    if (map) focusButton.addEventListener('click', () => focusEvent(index));
    card.appendChild(focusButton);

    const links = eventLinks(event);
    if (links.length) {
      const linkBox = document.createElement('div');
      linkBox.className = 'event-links';
      links.forEach((link, linkIndex) => {
        const anchor = document.createElement('a');
        anchor.href = link;
        anchor.target = '_blank';
        anchor.rel = 'noopener noreferrer';
        anchor.textContent = links.length > 1 ? `관련 링크 ${linkIndex + 1}` : '관련 링크';
        linkBox.appendChild(anchor);
      });
      card.appendChild(linkBox);
    }

    fragment.appendChild(card);
  });
  list.appendChild(fragment);
}

function renderMarkers(events) {
  clearMarkers();
  if (!map) return;

  events.forEach((event, index) => {
    const position = new naver.maps.LatLng(event.latitude, event.longitude);

    const marker = new naver.maps.Marker({
      position,
      map,
      title: event.name
    });

    // 말풍선은 HTML 문자열로 넘겨야 한다. 값에 <, & 같은 글자가 있어도 그대로
    // 보이도록(그리고 표시가 깨지지 않도록) 모두 이스케이프해서 넣는다.
    const esc = Stelline.escapeHtml;
    const links = eventLinks(event)
      .map(link => `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(link)}</a>`)
      .join('<br>');

    const content = `
      <div class="map-info">
        <strong>${esc(event.name)}</strong>
        장소: ${esc(event.location_name)}<br>
        기간: ${esc(formatDateRange(event.start_date, event.end_date))}
        ${links ? `<br>관련 링크<br>${links}` : ''}
      </div>
    `;

    const infowindow = new naver.maps.InfoWindow({ content });

    naver.maps.Event.addListener(marker, 'click', function () {
      if (openInfoWindow === infowindow) {
        infowindow.close();
        openInfoWindow = null;
        document.querySelectorAll('.event-card').forEach(card => card.classList.remove('is-on'));
      } else {
        focusEvent(index);
      }
    });

    entries.push({ event, marker, infowindow });
  });
}

function filterAndRender() {
  const showFuture = document.getElementById('showFutureEvents').checked;

  const filtered = allEvents.filter(e => {
    const start = new Date(e.start_date);
    const end = new Date(e.end_date);
    if (end < today) return false;
    if (e.always) return true;
    if (!showFuture && start > today) return false;
    return true;
  });

  renderMarkers(filtered);
  renderList(filtered);
}

function fetchEvents() {
  return Stelline.api("offline/offline_api", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  }).then(res => res.json());
}

function offlineRequest() {
  fetchEvents()
    .then(events => {
      allEvents = Array.isArray(events) ? events : [];
      filterAndRender();
    })
    .catch(err => {
      console.error(err);
      const list = document.getElementById('event-list');
      if (list) {
        list.innerHTML = '<p class="empty-state is-error">이벤트 목록을 불러오지 못했습니다.</p>';
      }
    });
}

window.onload = () => {
  initMap();           // ✅ 지도는 한 번만 초기화
  offlineRequest();    // 데이터 가져와서 마커 렌더링
  document.getElementById('showFutureEvents')
          .addEventListener('change', filterAndRender);
};

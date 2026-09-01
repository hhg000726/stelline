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

function initMap() {
  // 지도를 못 불러오는 상황에서도 목록은 그대로 보여 준다.
  if (!window.naver || !window.naver.maps) return;
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

  document.querySelectorAll('.event-card').forEach((card, cardIndex) => {
    card.classList.toggle('is-on', cardIndex === index);
  });

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
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'event-card';

    const name = document.createElement('strong');
    name.textContent = event.name || '오프라인 이벤트';
    card.appendChild(name);

    const place = document.createElement('span');
    place.className = 'event-place';
    place.textContent = event.location_name || event.address || '';
    card.appendChild(place);

    const date = document.createElement('span');
    date.className = 'event-date';
    date.textContent = formatDateRange(event.start_date, event.end_date);
    card.appendChild(date);

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
        // 링크를 눌렀을 때 카드(지도 이동)까지 실행되지 않게 막는다.
        anchor.addEventListener('click', clickEvent => clickEvent.stopPropagation());
        linkBox.appendChild(anchor);
      });
      card.appendChild(linkBox);
    }

    card.addEventListener('click', () => focusEvent(index));
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

    const links = eventLinks(event)
      .map(link => `<a href="${link}" target="_blank" rel="noopener noreferrer">${link}</a>`)
      .join('<br>');

    const content = `
      <div class="map-info">
        <strong>${event.name}</strong>
        장소: ${event.location_name}<br>
        기간: ${formatDateRange(event.start_date, event.end_date)}
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

const today = new Date();
let openInfoWindow = null;
let allEvents = [];
let map = null;
let markers = [];

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

function fetchEvents() {
  return fetch("https://stelline.site/api/offline/offline_api", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  }).then(res => res.json());
}

function initMap() {
  map = new naver.maps.Map('map', {
    center: new naver.maps.LatLng(36.5, 127.5),
    zoom: 7
  });
}

function clearMarkers() {
  markers.forEach(m => m.setMap(null));
  markers = [];
  openInfoWindow?.close();
  openInfoWindow = null;
}

function renderMarkers(events) {
  clearMarkers();

  events.forEach(event => {
    const position = new naver.maps.LatLng(event.latitude, event.longitude);

    const marker = new naver.maps.Marker({
      position,
      map,
      title: event.name
    });

    const links = event.description
      .split(',')
      .map(link => link.trim())
      .filter(link => link)
      .map(link => `<a href="${link}" target="_blank">${link}</a>`)
      .join('<br>');

    const content = `
      <div style="padding:10px;">
        <strong>${event.name}</strong><br>
        장소: ${event.location_name}<br>
        기간: ${formatDateRange(event.start_date, event.end_date)}<br>
        관련 링크<br>
        ${links}
      </div>
    `;

    const infowindow = new naver.maps.InfoWindow({ content });

    naver.maps.Event.addListener(marker, 'click', function () {
      if (openInfoWindow === infowindow) {
        infowindow.close();
        openInfoWindow = null;
      } else {
        openInfoWindow?.close();
        infowindow.open(map, marker);
        openInfoWindow = infowindow;
      }
    });

    markers.push(marker);
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
}

function offlineRequest() {
  fetchEvents()
    .then(events => {
      allEvents = events;
      filterAndRender();
    })
    .catch(err => {
      alert(`오류 발생: ${err.message}`);
      console.log(err);
    });
}

window.onload = () => {
  initMap();           // ✅ 지도는 한 번만 초기화
  offlineRequest();    // 데이터 가져와서 마커 렌더링
  document.getElementById('showFutureEvents')
          .addEventListener('change', filterAndRender);
};

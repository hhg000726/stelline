const today = new Date();
let openInfoWindow = null;
let allEvents = []; // 전체 이벤트 캐싱용

function formatDate(dateStr) {
  const date = new Date(dateStr);
  const year = date.getFullYear();
  if (year >= 3000) return "(미정)";
  return `${year}.${date.getMonth() + 1}.${date.getDate()}`;
}

function fetchEvents() {
  return fetch("https://stelline.site/api/offline/offline_api", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  }).then(res => res.json());
}

function renderMap(events) {
  const map = new naver.maps.Map('map', {
    center: new naver.maps.LatLng(36.5, 127.5),
    zoom: 7
  });

  events.forEach(event => {
    const position = new naver.maps.LatLng(event.latitude, event.longitude);

    const marker = new naver.maps.Marker({
      position: position,
      map: map,
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
        기간: ${formatDate(event.start_date)} ~ ${formatDate(event.end_date)}<br>
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
        if (openInfoWindow) openInfoWindow.close();
        infowindow.open(map, marker);
        openInfoWindow = infowindow;
      }
    });
  });
}

function filterAndRender() {
  const showFuture = document.getElementById('showFutureEvents').checked;

  const filtered = allEvents.filter(e => {
    const start = new Date(e.start_date);
    const end = new Date(e.end_date);
    if (end < today) return false;
    if (!showFuture && start > today) return false;
    return true;
  });

  renderMap(filtered);
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
  offlineRequest();
  document.getElementById('showFutureEvents').addEventListener('change', filterAndRender);
};

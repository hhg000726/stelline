const today = new Date();

function offlineRequest() {
  fetch("https://stelline.site/api/offline/offline_api", {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  })
    .then(response => response.json())
    .then(events => {

      var map = new naver.maps.Map('map', {
        center: new naver.maps.LatLng(36.5, 127.5),
        zoom: 7
      });

      // 이벤트 루프
      events
        .filter(e => new Date(e.end_date) >= today)
        .forEach(event => {
          const position = new naver.maps.LatLng(event.latitude, event.longitude);

          const marker = new naver.maps.Marker({
            position: position,
            map: map,
            title: event.name
          });

          const content = `
            <div style="padding:10px;">
              <strong>${event.name}</strong><br>
              장소: ${event.location_name}<br>
              기간: ${event.start_date} ~ ${event.end_date}<br>
              <p>${event.description}</p>
            </div>
          `;

          const infowindow = new naver.maps.InfoWindow({
            content: content
        });

        naver.maps.Event.addListener(marker, 'click', function() {
          infowindow.open(map, marker);
        });
      });
      
    })
    .catch((error) => {
      alert(`오류 발생: ${error.message}`);
      console.log(error);
    });
}
    
window.onload = offlineRequest;
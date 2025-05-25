// ⭐⭐⭐ [필수] 당신의 Firebase 프로젝트 구성으로 교체하세요! ⭐⭐⭐
const firebaseConfig = {
    apiKey: "AIzaSyDG7znUAyWQ9VAmOpQlmvESCZqv1yvgkAw",
    authDomain: "stelline-9d8ed.firebaseapp.com",
    projectId: "stelline-9d8ed",
    storageBucket: "stelline-9d8ed.firebasestorage.app",
    messagingSenderId: "605362996281",
    appId: "1:605362996281:web:1f57afbd388b8c3badb9e8",
    measurementId: "G-KLPSVS0VN4"
};

// ⭐⭐⭐ [필수] 당신의 웹 푸시 VAPID 공개 키로 교체하세요! ⭐⭐⭐
// Firebase 콘솔 -> 프로젝트 설정 -> Cloud Messaging 탭에서 "웹 구성" 아래에 있습니다.
const VAPID_KEY = "BARjqsXZvm70GJ12i6w6OPJX8U8v5fPdBG7r9pkwwNJL_MC7GXzdb4c-g_I2fPb5U_tTO0B5MlUzM0kWvcUHwIs";

// Firebase 초기화
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

const statusElement = document.getElementById('status');
const enableButton = document.getElementById('enableNotificationsButton');

/**
 * 1. Service Worker를 등록합니다.
 * 웹 푸시 알림은 Service Worker 없이는 작동하지 않습니다.
 */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/firebase-messaging-sw.js')
            .then((registration) => {
                console.log('Service Worker 등록 성공:', registration);
                // Service Worker 등록 성공 후 알림 상태 확인 및 UI 업데이트
                updateNotificationUI(); 
            })
            .catch((error) => {
                console.error('Service Worker 등록 실패:', error);
                statusElement.textContent = 'Service Worker 등록 실패. (HTTPS 및 경로 확인)';
                enableButton.disabled = true; // 실패 시 버튼 비활성화
                enableButton.textContent = '알림 지원 안됨'; // 버튼 텍스트 변경
            });
    } else {
        console.warn('이 브라우저는 Service Worker를 지원하지 않습니다.');
        statusElement.textContent = '이 브라우저는 웹 푸시 알림을 지원하지 않습니다.';
        enableButton.disabled = true;
        enableButton.textContent = '알림 지원 안됨'; // 버튼 텍스트 변경
    }
}

/**
 * 알림 권한 상태에 따라 UI를 업데이트하는 함수
 */
function updateNotificationUI() {
    if (Notification.permission === 'granted') {
        statusElement.textContent = '알림이 이미 허용되었습니다. 곧 알림을 받을 수 있습니다.';
        enableButton.disabled = true;
        enableButton.textContent = '알림 허용됨';
        enableButton.style.backgroundColor = '#28a745'; // 성공 색상 (선택 사항)
        enableButton.style.cursor = 'default';
        // 이미 허용된 상태이므로, 토큰 가져오기 함수도 실행 (새 토큰 또는 기존 토큰 확인)
        getExistingToken(); 
    } else if (Notification.permission === 'denied') {
        statusElement.textContent = '알림이 차단되었습니다. 브라우저 설정에서 해제해주세요.';
        enableButton.disabled = true;
        enableButton.textContent = '알림 차단됨';
        enableButton.style.backgroundColor = '#dc3545'; // 경고 색상 (선택 사항)
        enableButton.style.cursor = 'default';
    } else { // 'default' 또는 알 수 없는 상태
        statusElement.textContent = '앱 설치 없이 알림을 받으려면 버튼을 클릭하세요.';
        enableButton.disabled = false;
        enableButton.textContent = '알림 허용하기';
        enableButton.style.backgroundColor = '#007bff'; // 기본 색상 (선택 사항)
        enableButton.style.cursor = 'pointer';
    }
}


/**
 * 2. 알림 권한을 요청하고, FCM 토큰을 가져와 서버로 전송합니다.
 */
function requestPermissionAndGetToken() {
    enableButton.disabled = true; // 중복 클릭 방지

    // 알림 권한 요청
    Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
            console.log('알림 권한 승인됨.');
            statusElement.textContent = '알림 권한이 승인되었습니다.';
            enableButton.textContent = '토큰 가져오는 중...'; // 버튼 텍스트 변경

            // FCM 토큰 가져오기 (웹 푸시 구독 정보)
            messaging.getToken({ vapidKey: VAPID_KEY }).then((currentToken) => {
                if (currentToken) {
                    console.log('웹 푸시 토큰:', currentToken);
                    statusElement.textContent = `토큰 가져옴: ${currentToken.substring(0, 20)}...`;
                    enableButton.textContent = '토큰 서버 전송 중...'; // 버튼 텍스트 변경

                    // ⭐⭐⭐ [필수] 이 토큰을 당신의 백엔드 서버로 전송해야 합니다. ⭐⭐⭐
                    // `https://stelline.site/api/congratulation/register` 엔드포인트로 대체하세요.
                    sendTokenToServer(currentToken);

                } else {
                    console.warn('푸시 알림 토큰을 가져올 수 없습니다. 알림 권한이 없거나 다른 문제일 수 있습니다.');
                    statusElement.textContent = '토큰을 가져올 수 없습니다. 권한을 확인하세요.';
                    enableButton.disabled = false;
                    enableButton.textContent = '알림 허용하기 (재시도)'; // 버튼 텍스트 변경
                }
            }).catch((err) => {
                console.error('웹 푸시 토큰 가져오는 중 에러 발생:', err);
                statusElement.textContent = `토큰 가져오기 실패: ${err.message}`;
                enableButton.disabled = false;
                enableButton.textContent = '알림 허용하기 (재시도)'; // 버튼 텍스트 변경
            });
        } else {
            console.warn('알림 권한 거부됨.');
            statusElement.textContent = '알림 권한이 거부되었습니다.';
            enableButton.disabled = false;
            enableButton.textContent = '알림 허용하기 (거부됨)'; // 버튼 텍스트 변경
            enableButton.style.backgroundColor = '#dc3545'; // 경고 색상 (선택 사항)
        }
    });
}

/**
 * 이미 알림이 허용된 경우, 기존 토큰을 가져와 서버에 다시 전송하는 함수
 * (만약 토큰이 만료되었거나 변경되었을 경우를 대비)
 */
async function getExistingToken() {
    try {
        const currentToken = await messaging.getToken({ vapidKey: VAPID_KEY });
        if (currentToken) {
            console.log('기존 웹 푸시 토큰 확인:', currentToken);
            statusElement.textContent = `알림이 이미 허용되었습니다. (토큰: ${currentToken.substring(0, 20)}...)`;
            sendTokenToServer(currentToken); // 서버에 다시 전송하여 최신 상태 유지
        } else {
            console.warn('기존 토큰을 가져올 수 없습니다. 다시 시도해주세요.');
            updateNotificationUI(); // 권한 상태에 따라 UI 재조정
        }
    } catch (err) {
        console.error('기존 토큰 가져오는 중 에러:', err);
        updateNotificationUI(); // 에러 발생 시 UI 재조정
    }
}


/**
 * 서버에 웹 푸시 토큰을 전송하는 함수
 * 이 함수는 당신의 실제 백엔드 API와 연동되어야 합니다.
 */
async function sendTokenToServer(token) {
    const serverUrl = "https://stelline.site/api/congratulation/register"; // ⭐ 당신의 백엔드 API 엔드포인트
    try {
        const response = await fetch(serverUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: token, platform: 'web' }) // 웹 토큰임을 구분하기 위한 'platform' 필드 추가
        });

        if (response.ok) {
            console.log('웹 푸시 토큰 서버 전송 성공');
            statusElement.textContent = '토큰 서버 전송 성공! 이제 알림을 받을 수 있습니다.';
            enableButton.textContent = '알림 허용됨'; // 최종 성공 메시지
            enableButton.style.backgroundColor = '#28a745'; // 성공 색상
        } else {
            console.error('서버 에러:', response.status, response.statusText);
            statusElement.textContent = `서버 에러: ${response.status}`;
            enableButton.textContent = '알림 허용하기 (서버 오류)'; // 서버 오류 메시지
            enableButton.style.backgroundColor = '#dc3545'; // 오류 색상
        }
    } catch (error) {
        console.error('서버 전송 실패:', error);
        statusElement.textContent = `서버 전송 실패: ${error.message}`;
        enableButton.textContent = '알림 허용하기 (네트워크 오류)'; // 네트워크 오류 메시지
        enableButton.style.backgroundColor = '#dc3545'; // 오류 색상
    } finally {
        enableButton.disabled = false; // 작업 완료 후 버튼 다시 활성화 (재시도 가능)
        enableButton.style.cursor = 'default'; // 버튼 커서 변경
    }
}

/**
 * 3. 웹사이트가 열려 있을 때 (포그라운드) 메시지 수신 처리
 */
messaging.onMessage((payload) => {
    console.log('포그라운드 메시지 받음:', payload);

    const notificationTitle = payload.notification?.title || "새 알림";
    const notificationBody = payload.notification?.body || "내용 없음";
    const videoUrl = payload.data?.video_url; // FCM 데이터 페이로드에서 video_url 추출

    // 브라우저 내에서 팝업 또는 커스텀 UI로 알림 내용 표시
    alert(`[${notificationTitle}]\n${notificationBody}\n\n${videoUrl ? '유튜브 링크: ' + videoUrl : ''}`);

    // 포그라운드에서도 네이티브 알림을 보여주고 싶다면
    if (Notification.permission === 'granted') {
        navigator.serviceWorker.getRegistration().then(registration => {
            if (registration) {
                registration.showNotification(notificationTitle, {
                    body: notificationBody,
                    icon: '/firebase-logo.png', // 웹사이트에 표시될 아이콘 경로 (예: 웹사이트 루트에 있는 파비콘)
                    data: { video_url: videoUrl } // 알림 클릭 시 사용할 데이터
                });
            }
        });
    }
});


// ⭐ 페이지 로드 시 Service Worker 등록을 시도하고 UI를 업데이트합니다. ⭐
window.addEventListener('load', () => {
    registerServiceWorker();
    // 초기 로드 시에도 알림 상태에 따라 UI를 업데이트합니다.
    updateNotificationUI(); 
});

// 알림 허용 버튼 클릭 이벤트 리스너
enableButton.addEventListener('click', requestPermissionAndGetToken);

// 초기 상태에서 버튼 비활성화 (Service Worker 등록 후 활성화되도록)
enableButton.disabled = true;


// ⭐ iOS 사용자를 위한 추가 안내 (PWA 설치 유도) ⭐
// 이 부분은 UI/UX에 따라 적절하게 사용자에게 안내해야 합니다.
if (navigator.userAgent.match(/iPhone|iPad|iPod/i)) {
    // iOS 기기이면서 PWA로 설치되지 않은 경우
    if (!window.matchMedia('(display-mode: standalone)').matches && !navigator.standalone) {
        statusElement.innerHTML += '<br><b><span style="color: #dc3545;">🚨 iOS 사용자는 Safari에서 "홈 화면에 추가"해야 알림을 받을 수 있습니다.</span></b>';
        // 필요하다면, 홈 화면에 추가하는 방법을 안내하는 별도의 팝업이나 지시를 제공할 수 있습니다.
    }
}
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
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
}
const messaging = firebase.messaging();

const statusElement = document.getElementById('status');
const enableButton = document.getElementById('enableNotificationsButton');
const disableButton = document.getElementById('disableNotificationsButton');

// 초기 상태에서 버튼 비활성화 (스크립트 로드 시 바로 적용)
enableButton.disabled = true;
disableButton.disabled = true;

/**
 * 1. Service Worker를 등록합니다.
 * 웹 푸시 알림은 Service Worker 없이는 작동하지 않습니다.
 */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/firebase-messaging-sw.js')
            .then((registration) => {
                console.log('Service Worker 등록 성공:', registration);
                // Service Worker 등록 성공 후 UI 업데이트 (토큰 상태를 기반으로)
                // checkAndSetUIBasedOnToken()은 페이지 로드 시 호출되므로 여기서는 제거
            })
            .catch((error) => {
                console.error('Service Worker 등록 실패:', error);
                statusElement.textContent = 'Service Worker 등록 실패. (HTTPS 및 경로 확인)';
                statusElement.className = 'error';
                enableButton.disabled = true;
                enableButton.textContent = '알림 지원 안됨';
                disableButton.disabled = true;
                checkAndSetUIBasedOnToken(); // 서비스 워커 등록 실패 시 UI 상태 재조정
            });
    } else {
        console.warn('이 브라우저는 Service Worker를 지원하지 않습니다.');
        statusElement.textContent = '이 브라우저는 웹 푸시 알림을 지원하지 않습니다.';
        statusElement.className = 'error';
        enableButton.disabled = true;
        enableButton.textContent = '알림 지원 안됨';
        disableButton.disabled = true;
    }
}

async function checkAndSetUIBasedOnToken() {
    statusElement.className = 'info';

    const permission = Notification.permission; // 브라우저 알림 권한 확인

    if (permission === 'denied') {
        statusElement.textContent = '알림이 브라우저 설정에서 차단되었습니다. 새로고침 하거나 수동으로 설정해주세요.';
        statusElement.className = 'error';
        enableButton.disabled = true;
        enableButton.textContent = '알림 차단됨';
        enableButton.style.backgroundColor = '#dc3545';
        enableButton.style.cursor = 'default';
        disableButton.disabled = true;
        disableButton.textContent = '알림 취소 불가';
        disableButton.style.backgroundColor = '#cccccc';
        disableButton.style.cursor = 'not-allowed';
        return; // 일찍 종료
    }

    let currentToken = null;
    try {
        // Service Worker가 등록되지 않았거나 문제가 있다면 getToken은 실패할 수 있음.
        // 이 경우에는 try-catch 블록에서 처리되므로 여기서는 permission === 'granted'일 때만 getToken을 시도.
        if (permission === 'granted') { // 권한이 'granted'일 때만 토큰 가져오기 시도
            currentToken = await messaging.getToken({ vapidKey: VAPID_KEY });
        }
    } catch (err) {
        console.error('FCM 토큰 가져오는 중 오류 발생 (checkAndSetUIBasedOnToken):', err);
        statusElement.textContent = `알림 상태 확인 중 오류: ${err.message}`;
        statusElement.className = 'error';
        // 토큰 가져오기 실패 시, 다시 '알림 허용하기'를 누를 수 있도록 허용
        enableButton.disabled = false;
        enableButton.textContent = '알림 허용하기';
        enableButton.style.backgroundColor = '#007bff';
        enableButton.style.cursor = 'pointer';
        disableButton.disabled = true;
        disableButton.textContent = '알림 취소하기';
        disableButton.style.backgroundColor = '#cccccc';
        disableButton.style.cursor = 'not-allowed';
        return;
    }

    // ⭐ 핵심 수정 부분 ⭐
    if (await currentTokenIsValid(currentToken)) {
        // 토큰이 존재하면 알림이 활성화된 것으로 간주
        statusElement.textContent = '알림이 허용되었고, 토큰이 발급되었습니다.';
        statusElement.className = 'success';
        enableButton.disabled = true;
        enableButton.textContent = '알림 허용됨';
        enableButton.style.backgroundColor = '#28a745';
        enableButton.style.cursor = 'default';

        disableButton.disabled = false;
        disableButton.textContent = '알림 취소하기';
        disableButton.style.backgroundColor = '#6c757d';
        disableButton.style.cursor = 'pointer';
    } else { // permission === 'default' (아직 묻지 않음) 또는 그 외 토큰 없는 경우
        statusElement.textContent = '앱 설치 없이 알림을 받으려면 버튼을 클릭하세요.';
        enableButton.disabled = false;
        enableButton.textContent = '알림 허용하기';
        enableButton.style.backgroundColor = '#007bff';
        enableButton.style.cursor = 'pointer';

        disableButton.disabled = true;
        disableButton.textContent = '알림 취소하기';
        disableButton.style.backgroundColor = '#cccccc';
        disableButton.style.cursor = 'not-allowed';
    }
}

async function currentTokenIsValid(token) {
    if (!token) {
        return false;
    }

    const serverUrl = "/api/congratulation/check-token";
    try {
        const response = await fetch(serverUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: token, platform: 'web' })
        });

        if (response.ok) {
            const data = await response.json();
            return data.valid === true;
        } else {
            return false;
        }
    } catch (error) {
        console.error('서버 확인 실패:', error);
        statusElement.textContent = `서버 확인 실패: ${error.message}`;
        statusElement.className = 'error';
    }

    return false;
}

/**
 * 2. 알림 권한을 요청하고, FCM 토큰을 가져와 서버로 전송합니다.
 */
function requestPermissionAndGetToken() {
    enableButton.disabled = true; // 중복 클릭 방지
    disableButton.disabled = true; // 허용 과정 중 취소 버튼 비활성화

    // 알림 권한 요청
    Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
            console.log('알림 권한 승인됨. 토큰 가져오기 시도...');
            statusElement.textContent = '알림 권한이 승인되었습니다. 토큰 가져오는 중...';
            statusElement.className = 'info';
            enableButton.textContent = '토큰 가져오는 중...';

            // FCM 토큰 가져오기 (웹 푸시 구독 정보)
            messaging.getToken({ vapidKey: VAPID_KEY }).then((currentToken) => {
                if (currentToken) {
                    console.log('웹 푸시 토큰:', currentToken);
                    statusElement.textContent = `토큰 가져옴: ${currentToken.substring(0, 20)}... 서버 전송 중...`;
                    enableButton.textContent = '토큰 서버 전송 중...';

                    // ⭐⭐⭐ [필수] 이 토큰을 당신의 백엔드 서버로 전송해야 합니다. ⭐⭐⭐
                    sendTokenToServer(currentToken);

                } else {
                    console.warn('푸시 알림 토큰을 가져올 수 없습니다. 알림 권한이 없거나 다른 문제일 수 있습니다.');
                    statusElement.textContent = '토큰을 가져올 수 없습니다. 권한을 확인하세요.';
                    statusElement.className = 'error';
                    checkAndSetUIBasedOnToken(); // 실패 시 UI 상태 재조정
                }
            }).catch((err) => {
                console.error('웹 푸시 토큰 가져오는 중 에러 발생:', err);
                statusElement.textContent = `토큰 가져오기 실패: ${err.message}`;
                statusElement.className = 'error';
                checkAndSetUIBasedOnToken(); // 실패 시 UI 상태 재조정
            });
        } else {
            console.warn('알림 권한 거부됨.');
            statusElement.textContent = '알림 권한이 거부되었습니다.';
            statusElement.className = 'error';
            checkAndSetUIBasedOnToken(); // 권한 거부 시 UI 상태 재조정
        }
    });
}

/**
 * 서버에 웹 푸시 토큰을 전송하는 함수
 * 이 함수는 당신의 실제 백엔드 API와 연동되어야 합니다.
 */
async function sendTokenToServer(token) {
    const serverUrl = "/api/congratulation/register";
    try {
        const response = await fetch(serverUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: token, platform: 'web' })
        });

        if (response.ok) {
            console.log('웹 푸시 토큰 서버 전송 성공');
            statusElement.textContent = '토큰 서버 전송 성공! 이제 알림을 받을 수 있습니다.';
            statusElement.className = 'success';
        } else {
            console.error('서버 에러:', response.status, response.statusText);
            statusElement.textContent = `서버 에러: ${response.status}`;
            statusElement.className = 'error';
        }
    } catch (error) {
        console.error('서버 전송 실패:', error);
        statusElement.textContent = `서버 전송 실패: ${error.message}`;
        statusElement.className = 'error';
    } finally {
        // 토큰 전송 결과에 따라 UI를 업데이트
        checkAndSetUIBasedOnToken();
    }
}

/**
 * ⭐ 알림 취소(구독 해지) 기능 ⭐
 */
async function unsubscribeNotifications() {
    disableButton.disabled = true;
    enableButton.disabled = true;

    statusElement.textContent = '알림 구독을 해지하는 중...';
    statusElement.className = 'info';

    try {
        const currentToken = await messaging.getToken({ vapidKey: VAPID_KEY }); // 현재 활성화된 토큰 가져오기
        if (currentToken) {
            // 1. Firebase에서 구독 해지
            await messaging.deleteToken(currentToken);
            console.log('Firebase 구독 해지 성공');
            statusElement.textContent = 'Firebase에서 구독이 해지되었습니다. 서버에 알리는 중...';
            statusElement.className = 'info';

            // 2. 서버에서 토큰 삭제 (필수)
            const serverUrl = "/api/congratulation/unregister";
            const response = await fetch(serverUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token: currentToken, platform: 'web' })
            });

            if (response.ok) {
                console.log('웹 푸시 토큰 서버 삭제 성공');
                statusElement.textContent = '알림 구독이 완전히 취소되었습니다.';
                statusElement.className = 'info';
            } else {
                console.error('서버에서 토큰 삭제 실패:', response.status, response.statusText);
                statusElement.textContent = `서버에서 토큰 삭제 실패: ${response.status}`;
                statusElement.className = 'error';
            }
        } else {
            console.warn('구독 해지할 토큰이 없습니다. 이미 해지되었거나 알림이 허용되지 않았습니다.');
            statusElement.textContent = '구독 해지할 토큰이 없습니다.';
            statusElement.className = 'info';
        }
    } catch (error) {
        console.error('알림 구독 해지 중 에러 발생:', error);
        statusElement.textContent = `알림 구독 해지 실패: ${error.message}`;
        statusElement.className = 'error';
    } finally {
        // 구독 해지 후 UI 상태 업데이트 (버튼 상태 재조정)
        checkAndSetUIBasedOnToken();
    }
}

// 3. 웹사이트가 열려 있을 때 (포그라운드) 메시지 수신 처리 (이 부분은 변경 없음)
messaging.onMessage((payload) => {
    console.log('포그라운드 메시지 받음:', payload);

    const notificationTitle = payload.notification?.title || "새 알림";
    const notificationBody = payload.notification?.body || "내용 없음";
    const videoUrl = payload.data?.video_url;

    alert(`[${notificationTitle}]\n${notificationBody}\n\n${videoUrl ? '유튜브 링크: ' + videoUrl : ''}`);

    if (Notification.permission === 'granted') {
        navigator.serviceWorker.getRegistration().then(registration => {
            if (registration) {
                registration.showNotification(notificationTitle, {
                    body: notificationBody,
                    data: { video_url: videoUrl }
                });
            }
        });
    }
});


// ⭐ 페이지 로드 시 Service Worker 등록을 시도하고 UI를 업데이트합니다. ⭐
window.addEventListener('load', () => {
    registerServiceWorker();
    checkAndSetUIBasedOnToken(); // 페이지 로드 시에도 토큰 상태를 기반으로 UI를 업데이트
});

// 알림 허용 버튼 클릭 이벤트 리스너
enableButton.addEventListener('click', requestPermissionAndGetToken);
// 알림 취소 버튼 클릭 이벤트 리스너
disableButton.addEventListener('click', unsubscribeNotifications);

// ⭐ iOS 사용자를 위한 추가 안내 (PWA 설치 유도) ⭐
if (navigator.userAgent.match(/iPhone|iPad|iPod/i)) {
    if (!window.matchMedia('(display-mode: standalone)').matches && !navigator.standalone) {
        statusElement.innerHTML += '<br><b><span style="color: #dc3545;">🚨 iOS 사용자는 Safari에서 "홈 화면에 추가"해야 알림을 받을 수 있습니다.</span></b>';
    }
}

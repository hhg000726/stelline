// firebase-messaging-sw.js
// 이 파일은 웹사이트의 루트 디렉토리에 정확히 존재해야 합니다.
// 예: https://your-domain.com/firebase-messaging-sw.js

// Firebase SDK 스크립트 임포트 (최신 버전으로 업데이트 필요 시)
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

// ⭐⭐⭐ [필수] 당신의 Firebase 프로젝트 구성으로 교체하세요! ⭐⭐⭐
// app.js의 firebaseConfig와 동일해야 합니다.
const firebaseConfig = {
    apiKey: "AIzaSyDG7znUAyWQ9VAmOpQlmvESCZqv1yvgkAw",
    authDomain: "stelline-9d8ed.firebaseapp.com",
    projectId: "stelline-9d8ed",
    storageBucket: "stelline-9d8ed.firebasestorage.app",
    messagingSenderId: "605362996281",
    appId: "1:605362996281:web:1f57afbd388b8c3badb9e8",
    measurementId: "G-KLPSVS0VN4"
};

firebase.initializeApp(firebaseConfig);

const messaging = firebase.messaging();

/**
 * 백그라운드 메시지 수신 처리 (웹사이트가 닫혀 있거나 브라우저 백그라운드 상태일 때)
 */
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);

    const notificationTitle = payload.notification?.title || "새 알림";
    const notificationBody = payload.notification?.body || "내용 없음";
    // FCM 데이터 페이로드에서 video_url 추출. 서버에서 보낼 때 "data" 필드에 포함되어야 합니다.
    const videoUrl = payload.data?.video_url;

    const notificationOptions = {
        body: notificationBody,
        icon: '/firebase-logo.png', // ⭐ 웹사이트에 표시될 아이콘 경로 (권장: 웹사이트 루트에 192x192 이상 PNG 파일)
        data: { // 알림 클릭 시 전달될 사용자 정의 데이터
            video_url: videoUrl
        }
    };

    // 네이티브 시스템 알림을 표시합니다.
    return self.registration.showNotification(notificationTitle, notificationOptions);
});

/**
 * 알림 클릭 시 동작 정의
 */
self.addEventListener('notificationclick', (event) => {
    const clickedNotification = event.notification;
    clickedNotification.close(); // 알림 창 닫기

    const url = clickedNotification.data && clickedNotification.data.video_url;
    if (url) {
        // 알림 클릭 시 새 탭/창에서 YouTube URL 열기
        event.waitUntil(
            clients.openWindow(url)
        );
    } else {
        // video_url이 없으면 웹사이트의 기본 페이지 열기
        event.waitUntil(
            clients.openWindow('/') // 웹사이트의 홈 페이지 또는 특정 페이지
        );
    }
});
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
/**
 * 백그라운드 메시지 수신 처리 (웹사이트가 닫혀 있거나 브라우저 백그라운드 상태일 때)
 */
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);

    // payload.data에서 정보 추출
    const notificationTitle = payload.data?.title || "새 알림"; // data 필드에서 제목 가져오기
    const notificationBody = payload.data?.body || "내용 없음";   // data 필드에서 내용 가져오기
    const videoUrl = payload.data?.video_url; // data 필드에서 video_url 추출
    const imageUrl = payload.data?.image; // data 필드에서 이미지 URL 추출 (웹 푸시 icon/image용)

    const notificationOptions = {
        body: notificationBody,
        icon: imageUrl || '/firebase-logo.png', // 이미지 URL이 있다면 icon으로 사용, 없으면 기본 아이콘
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
        event.waitUntil(
            clients.openWindow(url) // 알림 클릭 시 새 탭/창에서 YouTube URL 열기 (웹용)
        );
    }
});
/* 브라우저 웹 푸시(FCM) 켜기·끄기.
 *
 * 예전 congratulation/app.js 를 그대로 옮긴 것이다. 부르는 순서, 서버에 보내는 형식
 * ({ token, platform: "web" }), 상태 문구, 버튼 이름과 잠김 여부까지 같다.
 * 달라진 것은 DOM 을 직접 만지는 대신 상태로 돌려주어 화면이 스스로 그린다는 점뿐이다.
 *
 * Firebase SDK 는 이 화면에 들어올 때 받아 온다. 예전에는 <script> 로 박아 두어
 * 알림을 쓰지 않는 사람도 늘 받아 왔다.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { loadScript } from "../../lib/loadScript";

const FIREBASE_APP = "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js";
const FIREBASE_MESSAGING = "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js";

const firebaseConfig = {
  apiKey: "AIzaSyDG7znUAyWQ9VAmOpQlmvESCZqv1yvgkAw",
  authDomain: "stelline-9d8ed.firebaseapp.com",
  projectId: "stelline-9d8ed",
  storageBucket: "stelline-9d8ed.firebasestorage.app",
  messagingSenderId: "605362996281",
  appId: "1:605362996281:web:1f57afbd388b8c3badb9e8",
  measurementId: "G-KLPSVS0VN4",
};

// Firebase 콘솔 → 프로젝트 설정 → Cloud Messaging 탭의 웹 푸시 인증서 공개 키.
const VAPID_KEY = "BARjqsXZvm70GJ12i6w6OPJX8U8v5fPdBG7r9pkwwNJL_MC7GXzdb4c-g_I2fPb5U_tTO0B5MlUzM0kWvcUHwIs";

const IOS_NOTE = '🚨 iOS 사용자는 Safari에서 "홈 화면에 추가"해야 알림을 받을 수 있습니다.';

const ENABLE_DEFAULT = { disabled: false, label: "알림 허용하기", state: null };
const DISABLE_DEFAULT = { disabled: true, label: "알림 취소하기" };

function isStandaloneIos() {
  if (!navigator.userAgent.match(/iPhone|iPad|iPod/i)) return false;
  return !window.matchMedia("(display-mode: standalone)").matches && !navigator.standalone;
}

export function useNotifications() {
  const [status, setStatus] = useState({ text: "", tone: "" });
  const [enableButton, setEnableButton] = useState({ disabled: true, label: "알림 허용하기", state: null });
  const [disableButton, setDisableButton] = useState({ disabled: true, label: "알림 취소하기" });
  // 예전에는 안내 줄 뒤에 덧붙였다가 다음 상태 갱신에서 지워졌다. 그 성질을 그대로 둔다.
  const [extraNote, setExtraNote] = useState(() => (isStandaloneIos() ? IOS_NOTE : ""));

  const messaging = useRef(null);

  /* 알림 상태 줄. 알릴 것이 있을 때만 안내 문구 자리를 대신한다.
     둘을 한 줄에 겹쳐 쓰면 상태가 안내 문구를 덮어써서 문구를 고칠 수가 없다. */
  const showStatus = useCallback((text, tone) => {
    setStatus({ text, tone: tone || "" });
    setExtraNote("");
  }, []);

  /* 알릴 것이 없는 평소 상태. 상태 줄을 접고 안내 문구를 그대로 보여 준다. */
  const resetStatus = useCallback(() => {
    setStatus({ text: "", tone: "" });
    setExtraNote("");
  }, []);

  const currentTokenIsValid = useCallback(
    async (token) => {
      if (!token) return false;
      try {
        const response = await fetch("/api/congratulation/check-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, platform: "web" }),
        });
        if (response.ok) {
          const data = await response.json();
          return data.valid === true;
        }
        return false;
      } catch (error) {
        console.error("서버 확인 실패:", error);
        showStatus(`서버 확인 실패: ${error.message}`, "is-error");
      }
      return false;
    },
    [showStatus],
  );

  const refreshUi = useCallback(async () => {
    const permission = Notification.permission;

    if (permission === "denied") {
      showStatus("알림이 브라우저 설정에서 차단되었습니다. 새로고침 하거나 수동으로 설정해주세요.", "is-error");
      setEnableButton({ disabled: true, label: "알림 차단됨", state: "is-blocked" });
      setDisableButton({ disabled: true, label: "알림 취소 불가" });
      return;
    }

    let currentToken = null;
    try {
      // 권한이 'granted' 일 때만 토큰을 물어본다. 그 밖에는 실패가 정상이라 묻지 않는다.
      if (permission === "granted" && messaging.current) {
        currentToken = await messaging.current.getToken({ vapidKey: VAPID_KEY });
      }
    } catch (error) {
      console.error("FCM 토큰 가져오는 중 오류 발생 (refreshUi):", error);
      showStatus(`알림 상태 확인 중 오류: ${error.message}`, "is-error");
      // 토큰 가져오기 실패 시, 다시 '알림 허용하기'를 누를 수 있도록 허용한다.
      setEnableButton(ENABLE_DEFAULT);
      setDisableButton(DISABLE_DEFAULT);
      return;
    }

    if (await currentTokenIsValid(currentToken)) {
      showStatus("알림이 허용되었고, 토큰이 발급되었습니다.", "is-success");
      setEnableButton({ disabled: true, label: "알림 허용됨", state: "is-active" });
      setDisableButton({ disabled: false, label: "알림 취소하기" });
    } else {
      resetStatus();
      setEnableButton(ENABLE_DEFAULT);
      setDisableButton(DISABLE_DEFAULT);
    }
  }, [currentTokenIsValid, resetStatus, showStatus]);

  const sendTokenToServer = useCallback(
    async (token) => {
      try {
        const response = await fetch("/api/congratulation/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, platform: "web" }),
        });
        if (response.ok) {
          showStatus("토큰 서버 전송 성공! 이제 알림을 받을 수 있습니다.", "is-success");
        } else {
          console.error("서버 에러:", response.status, response.statusText);
          showStatus(`서버 에러: ${response.status}`, "is-error");
        }
      } catch (error) {
        console.error("서버 전송 실패:", error);
        showStatus(`서버 전송 실패: ${error.message}`, "is-error");
      } finally {
        refreshUi();
      }
    },
    [refreshUi, showStatus],
  );

  const enable = useCallback(() => {
    // 중복 클릭 방지. 허용 과정 중에는 취소도 잠근다.
    setEnableButton((prev) => ({ ...prev, disabled: true }));
    setDisableButton((prev) => ({ ...prev, disabled: true }));

    Notification.requestPermission().then((permission) => {
      if (permission !== "granted") {
        console.warn("알림 권한 거부됨.");
        showStatus("알림 권한이 거부되었습니다.", "is-error");
        refreshUi();
        return;
      }

      showStatus("알림 권한이 승인되었습니다. 토큰 가져오는 중...", "is-info");
      setEnableButton((prev) => ({ ...prev, label: "토큰 가져오는 중..." }));

      messaging.current
        .getToken({ vapidKey: VAPID_KEY })
        .then((currentToken) => {
          if (!currentToken) {
            console.warn("푸시 알림 토큰을 가져올 수 없습니다.");
            showStatus("토큰을 가져올 수 없습니다. 권한을 확인하세요.", "is-error");
            refreshUi();
            return;
          }
          showStatus(`토큰 가져옴: ${currentToken.substring(0, 20)}... 서버 전송 중...`, "is-info");
          setEnableButton((prev) => ({ ...prev, label: "토큰 서버 전송 중..." }));
          sendTokenToServer(currentToken);
        })
        .catch((error) => {
          console.error("웹 푸시 토큰 가져오는 중 에러 발생:", error);
          showStatus(`토큰 가져오기 실패: ${error.message}`, "is-error");
          refreshUi();
        });
    });
  }, [refreshUi, sendTokenToServer, showStatus]);

  const disable = useCallback(async () => {
    setEnableButton((prev) => ({ ...prev, disabled: true }));
    setDisableButton((prev) => ({ ...prev, disabled: true }));
    showStatus("알림 구독을 해지하는 중...", "is-info");

    try {
      const currentToken = await messaging.current.getToken({ vapidKey: VAPID_KEY });
      if (currentToken) {
        // 1. Firebase 에서 구독 해지
        await messaging.current.deleteToken(currentToken);
        showStatus("Firebase에서 구독이 해지되었습니다. 서버에 알리는 중...", "is-info");

        // 2. 서버 DB 에서도 토큰 삭제(필수)
        const response = await fetch("/api/congratulation/unregister", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: currentToken, platform: "web" }),
        });
        if (response.ok) {
          showStatus("알림 구독이 완전히 취소되었습니다.", "is-info");
        } else {
          console.error("서버에서 토큰 삭제 실패:", response.status, response.statusText);
          showStatus(`서버에서 토큰 삭제 실패: ${response.status}`, "is-error");
        }
      } else {
        console.warn("구독 해지할 토큰이 없습니다.");
        showStatus("구독 해지할 토큰이 없습니다.", "is-info");
      }
    } catch (error) {
      console.error("알림 구독 해지 중 에러 발생:", error);
      showStatus(`알림 구독 해지 실패: ${error.message}`, "is-error");
    } finally {
      refreshUi();
    }
  }, [refreshUi, showStatus]);

  /* 화면에 들어오면 SDK 를 받아 초기화하고, 서비스 워커를 등록한 뒤 상태를 맞춘다. */
  useEffect(() => {
    let alive = true;

    async function start() {
      if (!("Notification" in window)) {
        showStatus("이 브라우저는 웹 푸시 알림을 지원하지 않습니다.", "is-error");
        setEnableButton({ disabled: true, label: "알림 지원 안됨", state: null });
        setDisableButton(DISABLE_DEFAULT);
        return;
      }

      try {
        await loadScript(FIREBASE_APP);
        await loadScript(FIREBASE_MESSAGING);
      } catch (error) {
        if (!alive) return;
        showStatus("알림 기능을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.", "is-error");
        setEnableButton({ disabled: true, label: "알림 지원 안됨", state: null });
        setDisableButton(DISABLE_DEFAULT);
        return;
      }
      if (!alive) return;

      if (!window.firebase.apps.length) window.firebase.initializeApp(firebaseConfig);
      messaging.current = window.firebase.messaging();

      // 웹 푸시 알림은 Service Worker 없이는 작동하지 않는다.
      if ("serviceWorker" in navigator) {
        try {
          await navigator.serviceWorker.register("/firebase-messaging-sw.js");
        } catch (error) {
          console.error("Service Worker 등록 실패:", error);
          if (!alive) return;
          showStatus("Service Worker 등록 실패. (HTTPS 및 경로 확인)", "is-error");
          setEnableButton({ disabled: true, label: "알림 지원 안됨", state: null });
          setDisableButton(DISABLE_DEFAULT);
          refreshUi();
          return;
        }
      } else {
        console.warn("이 브라우저는 Service Worker를 지원하지 않습니다.");
        showStatus("이 브라우저는 웹 푸시 알림을 지원하지 않습니다.", "is-error");
        setEnableButton({ disabled: true, label: "알림 지원 안됨", state: null });
        setDisableButton(DISABLE_DEFAULT);
        return;
      }

      // 웹사이트가 열려 있을 때(포그라운드) 받은 메시지.
      messaging.current.onMessage((payload) => {
        const notificationTitle = payload.notification?.title || "새 알림";
        const notificationBody = payload.notification?.body || "내용 없음";
        const videoUrl = payload.data?.video_url;

        window.alert(
          `[${notificationTitle}]\n${notificationBody}\n\n${videoUrl ? `유튜브 링크: ${videoUrl}` : ""}`,
        );

        if (Notification.permission === "granted") {
          navigator.serviceWorker.getRegistration().then((registration) => {
            if (registration) {
              registration.showNotification(notificationTitle, {
                body: notificationBody,
                data: { video_url: videoUrl },
              });
            }
          });
        }
      });

      if (alive) refreshUi();
    }

    start();
    return () => {
      alive = false;
    };
    // 화면에 들어올 때 한 번만 준비한다(SDK 받기·서비스 워커 등록·상태 맞추기).
    // 안에서 쓰는 함수들은 모두 상태 설정 함수만 붙들고 있어 다시 만들어지지 않는다.
  }, []);

  return { status, extraNote, enableButton, disableButton, enable, disable };
}

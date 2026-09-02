import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
/* 공용 배색·짜임은 관리자 화면(서버가 그리는 Jinja 문서)도 함께 쓴다. 파일을 옮기면
   두 벌이 되어 한쪽만 고쳐지므로, 있던 자리 그대로 두고 여기서 끌어다 쓴다. */
import "../../stelline/static/assets/site.css";
import "./styles/app.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {/* v7 에서 기본이 되는 두 가지를 미리 켠다. 켜 두지 않으면 브라우저 콘솔에
        경고가 두 줄씩 쌓이고, 나중에 올릴 때 동작이 조용히 달라진다.
        - startTransition: 화면을 옮기는 동안 이전 화면을 그대로 두어 덜 튄다.
        - relativeSplatPath: `*` 아래의 상대 주소 계산을 v7 규칙으로 맞춘다. */}
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  </StrictMode>,
);

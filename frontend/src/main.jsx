import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import App from "./App";
/* 공용 배색·짜임은 관리자 화면(서버가 그리는 Jinja 문서)도 함께 쓴다. 파일을 옮기면
   두 벌이 되어 한쪽만 고쳐지므로, 있던 자리 그대로 두고 여기서 끌어다 쓴다. */
import "../../stelline/static/assets/site.css";
import "./styles/app.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {/* v6 때 future flag 로 미리 켜 두던 두 가지(startTransition, relativeSplatPath)는
        v7 에서 기본 동작이 되어 따로 넘기지 않는다. */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);

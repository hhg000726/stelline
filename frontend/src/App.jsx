/* 주소와 화면의 짝짓기.
 *
 * 주소 구조는 예전 그대로다(/, /search, /karaoke, /congratulation, /offline).
 * 끝에 빗금이 붙은 주소(/search/)도 서버가 같은 문서를 내려주고, 여기 규칙도 그대로 받는다.
 * 화면 묶음은 React.lazy 로 나눠, 들어간 화면에 필요한 것만 받아 온다.
 */
import { lazy } from "react";
import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ContentProvider } from "./context/ContentContext";
import { NavButtonsProvider } from "./context/NavButtonsContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";

const MainPage = lazy(() => import("./pages/MainPage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const KaraokePage = lazy(() => import("./pages/KaraokePage"));
const CongratulationPage = lazy(() => import("./pages/CongratulationPage"));
const OfflinePage = lazy(() => import("./pages/OfflinePage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ContentProvider>
          <NavButtonsProvider>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<MainPage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/karaoke" element={<KaraokePage />} />
                <Route path="/congratulation" element={<CongratulationPage />} />
                <Route path="/offline" element={<OfflinePage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </NavButtonsProvider>
        </ContentProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

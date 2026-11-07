/* 주소와 화면의 짝짓기.
 *
 * 주소 구조는 예전 그대로다(/, /search, /karaoke, /congratulation, /offline).
 * 끝에 빗금이 붙은 주소(/search/)도 서버가 같은 문서를 내려주고, 여기 규칙도 그대로 받는다.
 * 화면 묶음은 React.lazy 로 나눠, 들어간 화면에 필요한 것만 받아 온다. 받아 오는 길과
 * 미리 받기·배포 뒤 새로 고침은 pages.js 가 맡는다.
 */
import { Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { ContentProvider } from "./context/ContentContext";
import { NavButtonsProvider } from "./context/NavButtonsContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import { NotFoundPage, PAGES } from "./pages";

const MainPage = PAGES["/"];
const SearchPage = PAGES["/search"];
const KaraokePage = PAGES["/karaoke"];
const CongratulationPage = PAGES["/congratulation"];
const OfflinePage = PAGES["/offline"];

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

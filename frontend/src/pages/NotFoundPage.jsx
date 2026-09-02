/* 없는 주소. 서버는 모르는 주소에 404를 주므로 여기까지 오는 일은 드물지만,
 * 화면 안에서 잘못 옮겨 갔을 때 빈 화면이 되지 않게 둔다. */
import { Link } from "react-router-dom";

import { usePageMeta } from "../lib/usePageMeta";

export default function NotFoundPage() {
  usePageMeta({ title: "찾을 수 없는 주소 · Stelline", description: "요청하신 주소를 찾지 못했습니다." });

  return (
    <section className="page-shell not-found">
      <h1 className="page-title">찾을 수 없는 주소입니다</h1>
      <p className="page-subtitle">주소를 다시 확인해 주세요.</p>
      <p>
        <Link className="btn-primary" to="/">
          메인으로 가기
        </Link>
      </p>
    </section>
  );
}

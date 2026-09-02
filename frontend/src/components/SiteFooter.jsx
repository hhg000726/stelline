/* 모든 화면 맨 아래 문구. 두 줄 모두 관리자 화면에서 고친다. */
import { ContentText } from "./ContentText";

export function SiteFooter() {
  return (
    <footer>
      <ContentText contentKey="site_footer_note" />
      <ContentText contentKey="site_footer_contact" />
    </footer>
  );
}

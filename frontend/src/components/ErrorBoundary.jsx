/* 화면 하나가 넘어져도 사이트 전체가 빈 화면이 되지 않게 막는다.
 *
 * 바깥에서 불러오는 것들(지도·캡차·알림 SDK)은 우리가 고칠 수 없는 자리에서 갑자기
 * 멈출 수 있다. 예전에는 화면마다 문서가 따로라 한 화면의 사고가 그 화면에서 끝났지만,
 * 한 문서 안에서 화면을 바꾸는 지금은 막아 주지 않으면 사이트가 통째로 사라진다.
 */
import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error("화면을 그리다 멈췄습니다:", error, info);
  }

  componentDidUpdate(previousProps) {
    // 다른 화면으로 옮겨 가면 다시 그려 본다. 한 번 넘어졌다고 계속 막아 둘 이유가 없다.
    if (this.state.failed && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <section className="page-shell not-found">
        <h1 className="page-title">화면을 여는 중 문제가 생겼습니다</h1>
        <p className="page-subtitle">새로고침하거나 잠시 후 다시 시도해 주세요.</p>
      </section>
    );
  }
}

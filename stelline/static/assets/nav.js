/* 화면 이동 메뉴의 표시 여부·순서.
 *
 * 관리자 화면의 `메인 화면 버튼`(main_buttons) 설정 하나로 메인 화면의 기능 카드와
 * 모든 화면 위쪽 머리말 메뉴가 함께 움직인다. 한쪽에서 숨긴 기능이 다른 쪽에 남아
 * 있으면 안 되기 때문이다.
 *
 * 버튼 이름은 [data-button-label]이 있는 곳에만 반영한다. 머리말은 자리가 좁아
 * 짧은 이름을 그대로 쓰고, 표시 여부와 순서만 따라간다.
 */
(function () {
  "use strict";

  var CACHE_KEY = "stelline.main.buttons";

  function containers() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-button-nav]"));
  }

  function apply(buttons) {
    if (!Array.isArray(buttons) || !buttons.length) return;

    var ordered = buttons.slice().sort(function (a, b) {
      return (a.order || 0) - (b.order || 0);
    });

    containers().forEach(function (container) {
      var nodes = new Map();
      container.querySelectorAll("[data-button-key]").forEach(function (node) {
        nodes.set(node.dataset.buttonKey, node);
      });

      ordered.forEach(function (config) {
        // DB에 없는 키는 손대지 않는다. 화면에 새 항목을 먼저 넣어도 사라지지 않는다.
        var node = nodes.get(config.key);
        if (!node) return;
        node.hidden = !config.visible;
        var labelNode = node.querySelector("[data-button-label]");
        if (labelNode && config.label) labelNode.textContent = config.label;
        container.appendChild(node);
      });
    });
  }

  function readCache() {
    try {
      var cached = window.localStorage.getItem(CACHE_KEY);
      return cached ? JSON.parse(cached) : null;
    } catch (error) {
      return null;
    }
  }

  function writeCache(buttons) {
    try {
      window.localStorage.setItem(CACHE_KEY, JSON.stringify(buttons));
    } catch (error) {
      /* 저장소를 못 쓰는 환경에서는 그냥 넘어간다. */
    }
  }

  function load() {
    if (!containers().length) return;

    // 지난번 설정을 먼저 반영해, 숨긴 항목이 잠깐 보였다 사라지지 않게 한다.
    apply(readCache());

    window.Stelline.api("main/buttons")
      .then(function (response) { return response.json(); })
      .then(function (buttons) {
        var list = Array.isArray(buttons) ? buttons : [];
        apply(list);
        // 조회 실패 시 빈 목록이 오는데, 이걸 저장하면 다음 방문에서 숨긴 항목이 잠깐 보인다.
        if (list.length) writeCache(list);
      })
      .catch(function (error) {
        // 설정을 못 받아오면 HTML에 적힌 기본 상태(전부 표시)를 그대로 둔다.
        console.error("메뉴 설정 로드 실패:", error);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();

(function () {
  "use strict";

  /* escapeHtml이 바꿔치기할 문자표.
   *
   * 예전 방식(<span>.textContent -> .innerHTML)이 내놓던 것과 같은 결과를 내되,
   * 따옴표 두 종류를 더 막아 속성값에 그대로 넣어도 안전하게 한다.
   * 마지막 항목은 줄바꿈 없는 공백(U+00A0)이다. */
  var ENTITIES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
    "\u00a0": "&nbsp;",
  };

  var ESCAPE_RE = /[&<>"'\u00a0]/g;

  function escape(character) {
    return ENTITIES[character];
  }

  /* ---------- 알림 말풍선 ----------
   * 복사처럼 화면이 그대로인 동작은 알려 주지 않으면 눌렸는지조차 알 수 없다.
   * 화면마다 따로 만들면 위치와 사라지는 시간이 어긋나므로 한 곳에서 만든다. */

  var toastNode = null;
  var toastTimers = [];

  function clearToastTimers() {
    toastTimers.forEach(window.clearTimeout);
    toastTimers = [];
  }

  function ensureToast() {
    if (toastNode && toastNode.isConnected) return toastNode;
    toastNode = document.createElement("div");
    toastNode.className = "site-toast";
    toastNode.id = "site-toast";
    // 스스로 읽어 주되, 말풍선이 뜨기 전의 빈 상태를 읽지는 않게 한다.
    toastNode.setAttribute("role", "status");
    toastNode.setAttribute("aria-live", "polite");
    toastNode.hidden = true;
    document.body.appendChild(toastNode);
    return toastNode;
  }

  function toast(message) {
    if (!message) return;
    // <body>가 아직 없으면 만들 자리가 없다. 준비된 뒤에 띄운다.
    if (!document.body) {
      document.addEventListener("DOMContentLoaded", function () { toast(message); });
      return;
    }
    var node = ensureToast();
    node.textContent = message;
    node.hidden = false;
    // hidden 을 막 벗겨낸 프레임에 클래스를 같이 붙이면 전환이 생략된다. 배치를 한 번
    // 읽어 강제로 반영시킨 뒤에 붙인다. (requestAnimationFrame 은 탭이 가려져 있으면
    // 아예 실행되지 않아, 말풍선이 투명한 채로 사라지는 일이 생긴다.)
    void node.offsetWidth;
    node.classList.add("is-visible");
    clearToastTimers();
    toastTimers.push(window.setTimeout(function () {
      node.classList.remove("is-visible");
      toastTimers.push(window.setTimeout(function () { node.hidden = true; }, 200));
    }, 1800));
  }

  /* ---------- 클립보드 ----------
   * navigator.clipboard 는 https 가 아니거나 권한이 막히면 조용히 실패한다.
   * 그때 아무 일도 일어나지 않으면 사용자는 눌러도 안 된다고만 느끼므로,
   * 예전 방식으로 한 번 더 시도하고 성공 여부를 돌려준다. */
  async function copyText(text) {
    var value = String(text == null ? "" : text);
    if (!value) return false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch (error) {
      /* 아래 대체 방법으로 넘어간다. */
    }
    try {
      var helper = document.createElement("textarea");
      helper.value = value;
      helper.setAttribute("readonly", "");
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      var copied = document.execCommand("copy");
      document.body.removeChild(helper);
      return copied;
    } catch (error) {
      return false;
    }
  }

  window.Stelline = {
    api(path, options = {}) {
      return fetch(`/api/${path.replace(/^\//, "")}`, options);
    },
    /* 예전에는 호출마다 <span>을 만들어 브라우저에 이스케이프를 맡겼다. 목록 한 번을
     * 그리는 데 버릴 DOM 노드를 수백 개 만드는 셈이라, 문자 치환 한 번으로 대신한다. */
    escapeHtml(value) {
      return String(value ?? "").replace(ESCAPE_RE, escape);
    },
    copyText,
    toast,
    icon(name) {
      const paths = {
        play: '<polygon points="5 3 19 12 5 21 5 3"></polygon>',
        bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path>',
        search: '<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>',
        mic: '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line>',
      };
      return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ""}</svg>`;
    },
  };
})();

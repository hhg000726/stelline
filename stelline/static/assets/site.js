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

  window.Stelline = {
    api(path, options = {}) {
      return fetch(`/api/${path.replace(/^\//, "")}`, options);
    },
    /* 예전에는 호출마다 <span>을 만들어 브라우저에 이스케이프를 맡겼다. 목록 한 번을
     * 그리는 데 버릴 DOM 노드를 수백 개 만드는 셈이라, 문자 치환 한 번으로 대신한다. */
    escapeHtml(value) {
      return String(value ?? "").replace(ESCAPE_RE, escape);
    },
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

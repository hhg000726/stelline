/* 관리자 화면에서 고치는 고정 문구·그림.
 *
 * HTML에는 지금까지처럼 기본 문구가 그대로 적혀 있다. 이 파일은 관리자가 바꾼 값이
 * 있을 때만 그 자리를 덮어쓴다. 그래서 API가 실패하거나 DB가 비어 있어도 화면은
 * 원래 모습 그대로 보인다. 빈 화면이 되는 경우는 없다.
 *
 * 붙이는 표시
 *   data-content-key="<키>"    이 요소의 문구(또는 그림 주소)를 바꾼다.
 *   data-content-hide="<선택자>" 값이 비면 이 요소 대신 가까운 바깥 상자를 숨긴다.
 *   data-content-list           여러 줄 문구를 <li> 목록으로 그린다.
 *   data-content-block          안의 문구가 모두 비면 이 상자를 통째로 숨긴다.
 *   data-step-grid              안에 남은 단계의 STEP 번호를 다시 매긴다.
 */
(function () {
  "use strict";

  var CACHE_KEY = "stelline.site.contents";

  function nodes() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-content-key]"));
  }

  /* 값이 비었을 때 사라져야 하는 요소. 그림 한 장이 아니라 그 그림이 든 칸이
     통째로 없어져야 하는 자리가 있어서, 어디를 숨길지 HTML이 정하게 둔다. */
  function hideTarget(node) {
    var selector = node.dataset.contentHide;
    if (!selector) return node;
    return node.closest(selector) || node;
  }

  /* 여러 줄 문구를 줄바꿈까지 살려 넣는다. innerHTML을 쓰지 않아 무엇이 들어와도 글자로만 남는다. */
  function setLines(node, value) {
    node.textContent = "";
    value.split("\n").forEach(function (line, index) {
      if (index) node.appendChild(document.createElement("br"));
      node.appendChild(document.createTextNode(line));
    });
  }

  function setList(node, value) {
    node.textContent = "";
    value.split("\n").forEach(function (line) {
      var listItem = document.createElement("li");
      listItem.textContent = line;
      node.appendChild(listItem);
    });
  }

  function applyOne(node, item) {
    var target = hideTarget(node);
    if (item.hidden || !item.value) {
      target.hidden = true;
      return;
    }
    target.hidden = false;
    node.hidden = false;

    if (item.type === "image") {
      // 그림 요소가 아닌 곳에 그림 키를 붙이는 실수는 조용히 넘긴다(주소가 글자로 보이는 것보다 낫다).
      if (node.tagName === "IMG") node.src = item.value;
      return;
    }
    if (node.hasAttribute("data-content-list")) setList(node, item.value);
    else setLines(node, item.value);
  }

  /* 안의 문구가 모두 비면 상자째 없앤다. 제목만 사라지고 빈 테두리가 남는 일을 막는다. */
  function applyBlocks() {
    document.querySelectorAll("[data-content-block]").forEach(function (block) {
      var parts = Array.prototype.slice.call(block.querySelectorAll("[data-content-key]"));
      if (!parts.length) return;
      block.hidden = parts.every(function (part) { return hideTarget(part).hidden; });
    });
  }

  /* 단계 하나를 지우면 STEP 1, STEP 3 처럼 번호가 비어 버린다. 남은 것만 다시 센다. */
  function renumberSteps() {
    document.querySelectorAll("[data-step-grid]").forEach(function (grid) {
      var step = 0;
      grid.querySelectorAll("[data-step-number]").forEach(function (label) {
        var stage = label.closest(".stage");
        if (stage && stage.hidden) return;
        step += 1;
        label.textContent = "STEP " + step;
      });
    });
  }

  function apply(items) {
    if (!items || typeof items !== "object") return;
    nodes().forEach(function (node) {
      var item = items[node.dataset.contentKey];
      // 모르는 키는 손대지 않는다. HTML에 새 자리를 먼저 만들어 두어도 사라지지 않는다.
      if (item) applyOne(node, item);
    });
    applyBlocks();
    renumberSteps();
  }

  function readCache() {
    try {
      var cached = window.localStorage.getItem(CACHE_KEY);
      return cached ? JSON.parse(cached) : null;
    } catch (error) {
      return null;
    }
  }

  function writeCache(items) {
    try {
      window.localStorage.setItem(CACHE_KEY, JSON.stringify(items));
    } catch (error) {
      /* 저장소를 못 쓰는 환경에서는 그냥 넘어간다. */
    }
  }

  function load() {
    if (!nodes().length) return;

    // 지난번 값을 먼저 반영해, 관리자가 지운 문구가 잠깐 보였다 사라지지 않게 한다.
    apply(readCache());

    window.Stelline.api("content")
      .then(function (response) { return response.json(); })
      .then(function (items) {
        apply(items);
        if (items && Object.keys(items).length) writeCache(items);
      })
      .catch(function (error) {
        // 값을 못 받아오면 HTML에 적힌 기본 문구를 그대로 둔다.
        console.error("사이트 콘텐츠 로드 실패:", error);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();

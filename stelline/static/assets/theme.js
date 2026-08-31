/* 사이트 전역 다크 모드.
 *
 * 모든 화면의 <head>에서 먼저 실행해 화면이 그려지기 전에 테마를 정한다.
 * (본문 뒤에서 켜면 밝은 화면이 한 번 번쩍인다.)
 * 고른 값은 브라우저에 남기고, 고른 적이 없으면 운영체제 설정을 따라간다.
 */
(function () {
    "use strict";

    var STORAGE_KEY = "stelline.theme";
    var THEMES = ["light", "dark"];
    var root = document.documentElement;

    var ICONS = {
        // 다크 모드일 때는 "밝게 되돌리기"를 뜻하는 해 아이콘을 보여준다.
        dark: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>',
        light: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path></svg>',
    };

    function readStored() {
        try {
            var saved = window.localStorage.getItem(STORAGE_KEY);
            return THEMES.indexOf(saved) >= 0 ? saved : null;
        } catch (error) {
            return null;
        }
    }

    function writeStored(theme) {
        try {
            window.localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            /* 저장이 막힌 환경에서도 이번 방문 동안은 그대로 쓴다. */
        }
    }

    function systemTheme() {
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    var chosen = readStored();
    var current = chosen || systemTheme();

    function paint() {
        root.setAttribute("data-theme", current);
        var button = document.getElementById("theme-toggle");
        if (!button) return;
        var toDark = current !== "dark";
        button.innerHTML = ICONS[current];
        button.setAttribute("aria-pressed", String(current === "dark"));
        button.setAttribute("aria-label", toDark ? "다크 모드 켜기" : "다크 모드 끄기");
        button.setAttribute("title", toDark ? "다크 모드 켜기" : "다크 모드 끄기");
    }

    function apply(theme, remember) {
        current = THEMES.indexOf(theme) >= 0 ? theme : "light";
        if (remember) {
            chosen = current;
            writeStored(current);
        }
        paint();
    }

    paint();

    function addToggle() {
        if (document.getElementById("theme-toggle")) return;
        var button = document.createElement("button");
        button.id = "theme-toggle";
        button.type = "button";
        button.className = "theme-toggle";
        button.addEventListener("click", function () {
            apply(current === "dark" ? "light" : "dark", true);
        });
        document.body.appendChild(button);
        paint();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", addToggle);
    } else {
        addToggle();
    }

    // 직접 고른 적이 없으면 운영체제 설정을 그대로 따라간다.
    if (window.matchMedia) {
        var query = window.matchMedia("(prefers-color-scheme: dark)");
        var onChange = function (event) {
            if (!chosen) apply(event.matches ? "dark" : "light", false);
        };
        if (query.addEventListener) query.addEventListener("change", onChange);
        else if (query.addListener) query.addListener(onChange);
    }

    // 화면별 스크립트에서 테마를 읽거나 바꿔야 할 때 쓴다.
    window.StellineTheme = {
        current: function () { return current; },
        isExplicit: function () { return Boolean(chosen); },
        set: function (theme) { apply(theme, true); },
    };
})();

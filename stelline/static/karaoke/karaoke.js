/* 노래방 번호 페이지.
 *
 * 곡 목록은 한 번만 받아 두고 검색·필터·정렬은 모두 브라우저에서 처리한다.
 * 즐겨찾기와 부를 곡 목록은 로그인 없이 쓰도록 브라우저 저장소에만 남긴다.
 */
(function () {
    "use strict";

    const STORAGE_KEYS = {
        favorites: "stelline.karaoke.favorites",
        setlist: "stelline.karaoke.setlist",
        machine: "stelline.karaoke.machine",
        mode: "stelline.karaoke.mode",
        cache: "stelline.karaoke.cache",
    };

    const SECTION_LABELS = { group: "단체", unit: "유닛", collab: "콜라보", gift: "기프트", solo: "개인" };
    const CATEGORY_LABELS = { original: "오리지널", cover: "커버" };
    const MACHINE_LABELS = { tj: "TJ", ky: "금영" };
    const SECTION_ORDER = ["group", "unit", "collab", "gift", "solo"];
    const CHOSEONG = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
    const CHOSEONG_ONLY = /^[ㄱ-ㅎ]+$/;
    const KEY_SEPARATOR = "␟";

    const state = {
        query: "",
        machine: "both",
        sort: "recent",
        members: new Set(),
        sections: new Set(),
        categories: new Set(),
        onlyNumbered: false,
        onlyFavorites: false,
    };

    let songs = [];
    let members = [];
    let favorites = new Set();
    let setlist = [];
    let visibleSongs = [];
    let usingCache = false;
    const songByKey = new Map();
    const songById = new Map();

    const el = {};

    /* ---------- 저장소 ---------- */

    function readStore(key, fallback) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw === null ? fallback : JSON.parse(raw);
        } catch (error) {
            return fallback;
        }
    }

    function writeStore(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            /* 저장 공간이 없거나 차단된 환경에서도 화면은 그대로 동작해야 한다. */
        }
    }

    /* ---------- 검색 문자열 ---------- */

    function normalizeText(value) {
        return String(value || "").toLowerCase().replace(/[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣぁ-んァ-ヺ一-龥]/g, "");
    }

    function toChoseong(value) {
        let result = "";
        for (const character of value) {
            const code = character.charCodeAt(0);
            if (code >= 0xac00 && code <= 0xd7a3) {
                result += CHOSEONG[Math.floor((code - 0xac00) / 588)];
            } else {
                result += character;
            }
        }
        return result;
    }

    function prepareQuery(raw) {
        const normalized = normalizeText(raw);
        return {
            raw: String(raw || "").trim(),
            normalized,
            isChoseong: normalized.length > 0 && CHOSEONG_ONLY.test(normalized),
        };
    }

    function songKey(song) {
        return song.title + KEY_SEPARATOR + song.artist;
    }

    function decorate(song) {
        const searchText = normalizeText([song.title, song.titleAlt, song.artist, (song.members || []).join(" "), song.note, song.tj, song.ky].join(" "));
        return Object.assign({}, song, {
            key: songKey(song),
            searchText,
            searchChoseong: toChoseong(searchText),
        });
    }

    /* ---------- 필터·정렬 ---------- */

    function hasNumber(song) {
        if (state.machine === "tj") return Boolean(song.tj);
        if (state.machine === "ky") return Boolean(song.ky);
        return Boolean(song.tj || song.ky);
    }

    function matchesQuery(song, query) {
        if (!query.normalized) return true;
        if (query.isChoseong) return song.searchChoseong.includes(query.normalized);
        return song.searchText.includes(query.normalized);
    }

    function sortValue(song) {
        const candidates = [];
        if (state.machine !== "ky" && song.tj) candidates.push(Number(song.tj));
        if (state.machine !== "tj" && song.ky) candidates.push(Number(song.ky));
        return candidates.length ? Math.min.apply(null, candidates) : Number.POSITIVE_INFINITY;
    }

    function applyFilters() {
        const query = prepareQuery(state.query);
        const filtered = songs.filter((song) => {
            if (state.onlyFavorites && !favorites.has(song.key)) return false;
            if (state.onlyNumbered && !hasNumber(song)) return false;
            if (state.sections.size && !state.sections.has(song.section)) return false;
            if (state.categories.size && !state.categories.has(song.category)) return false;
            if (state.members.size && !(song.members || []).some((name) => state.members.has(name))) return false;
            return matchesQuery(song, query);
        });

        if (state.sort === "title") {
            filtered.sort((a, b) => a.title.localeCompare(b.title, "ko"));
        } else if (state.sort === "number") {
            filtered.sort((a, b) => {
                const left = sortValue(a);
                const right = sortValue(b);
                // 번호가 없는 곡은 값이 Infinity라 뒤로 밀리고, 서로 같으면 곡명 순으로 둔다.
                return left !== right ? left - right : a.title.localeCompare(b.title, "ko");
            });
        } else {
            filtered.sort((a, b) => a.sortOrder - b.sortOrder);
        }
        return { list: filtered, query };
    }

    /* ---------- 그리기 ---------- */

    function esc(value) {
        // 공용 escapeHtml은 따옴표를 남겨 두므로, 속성값에도 그대로 넣을 수 있게 함께 바꾼다.
        return window.Stelline.escapeHtml(value).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function highlight(text, query) {
        if (!query.raw) return esc(text);
        const index = text.toLowerCase().indexOf(query.raw.toLowerCase());
        if (index < 0) return esc(text);
        return esc(text.slice(0, index))
            + "<mark>" + esc(text.slice(index, index + query.raw.length)) + "</mark>"
            + esc(text.slice(index + query.raw.length));
    }

    function numberButton(song, machine) {
        const value = machine === "tj" ? song.tj : song.ky;
        const label = MACHINE_LABELS[machine];
        let emphasis = "is-primary";
        if (state.machine !== "both" && state.machine !== machine) emphasis = "is-secondary";
        if (!value) {
            return `<span class="num-btn is-empty ${emphasis}"><span class="num-label">${label}</span><span class="num-value">없음</span></span>`;
        }
        return `<button type="button" class="num-btn ${emphasis}" data-action="copy" data-number="${esc(value)}" data-machine="${machine}" title="${label} ${esc(value)} 복사">`
            + `<span class="num-label">${label}</span><span class="num-value">${esc(value)}</span></button>`;
    }

    function songCard(song, query) {
        const isFavorite = favorites.has(song.key);
        const inSetlist = setlist.includes(song.key);
        const tags = [SECTION_LABELS[song.section] || song.section, CATEGORY_LABELS[song.category] || song.category];
        const footnotes = [song.note, song.releaseDate ? `${song.releaseDate} 발매` : ""].filter(Boolean);
        return `<article class="song-card" data-key="${esc(song.key)}">
      <div class="song-main">
        <p class="song-title">${highlight(song.title, query)}</p>
        <p class="song-meta"><span class="song-artist">${highlight(song.artist, query)}</span>${tags.map((tag) => `<span class="song-tag">${esc(tag)}</span>`).join("")}</p>
        ${footnotes.length ? `<p class="song-note">${esc(footnotes.join(" · "))}</p>` : ""}
      </div>
      <div class="song-numbers">${numberButton(song, "tj")}${numberButton(song, "ky")}</div>
      <div class="song-actions">
        <button type="button" class="icon-btn${isFavorite ? " is-on" : ""}" data-action="favorite" aria-pressed="${isFavorite}" title="즐겨찾기">${isFavorite ? "★" : "☆"}</button>
        <button type="button" class="icon-btn${inSetlist ? " is-on" : ""}" data-action="setlist" aria-pressed="${inSetlist}" title="부를 곡 목록에 담기">${inSetlist ? "−" : "+"}</button>
      </div>
    </article>`;
    }

    function renderList() {
        const { list, query } = applyFilters();
        visibleSongs = list;

        if (!songs.length) {
            el.songList.innerHTML = '<p class="empty-state">등록된 곡이 없습니다.</p>';
            el.resultCount.textContent = "";
            return;
        }
        if (!list.length) {
            el.songList.innerHTML = '<p class="empty-state">조건에 맞는 곡이 없습니다. 검색어나 필터를 바꿔보세요.</p>';
        } else {
            el.songList.innerHTML = list.map((song) => songCard(song, query)).join("");
        }

        const numbered = list.filter(hasNumber).length;
        el.resultCount.textContent = `${list.length}곡 (번호 있는 곡 ${numbered}곡 / 전체 ${songs.length}곡)`;
        el.randomPick.disabled = list.length === 0;
    }

    function memberChip(member) {
        // 유닛을 옮긴 멤버는 이전 유닛으로도 찾을 수 있게 안내만 남긴다.
        const formerUnits = member.formerUnits || [];
        const title = formerUnits.length ? ` title="${esc(member.name + " (구 " + formerUnits.join(" · ") + ")")}"` : "";
        return `<button type="button" class="kara-chip" data-filter="member" data-value="${esc(member.name)}"${title}>${esc(member.name)}</button>`;
    }

    function renderChips() {
        const unitGroups = new Map();
        members.forEach((member) => {
            const unit = member.unit || "기타";
            if (!unitGroups.has(unit)) unitGroups.set(unit, []);
            unitGroups.get(unit).push(member);
        });

        el.memberChips.innerHTML = Array.from(unitGroups.entries()).map(([unit, group]) => (
            `<div class="kara-chip-row"><span class="kara-chip-unit">${esc(unit)}</span>`
            + group.map(memberChip).join("")
            + "</div>"
        )).join("");

        const usedSections = SECTION_ORDER.filter((section) => songs.some((song) => song.section === section));
        el.sectionChips.innerHTML = usedSections
            .map((section) => `<button type="button" class="kara-chip" data-filter="section" data-value="${section}">${esc(SECTION_LABELS[section] || section)}</button>`)
            .join("");
        el.categoryChips.innerHTML = Object.keys(CATEGORY_LABELS)
            .map((category) => `<button type="button" class="kara-chip" data-filter="category" data-value="${category}">${esc(CATEGORY_LABELS[category])}</button>`)
            .join("");
        syncChipStates();
    }

    function syncChipStates() {
        el.filterPanel.querySelectorAll("[data-filter]").forEach((chip) => {
            const group = chip.dataset.filter === "member" ? state.members : chip.dataset.filter === "section" ? state.sections : state.categories;
            chip.classList.toggle("is-on", group.has(chip.dataset.value));
            chip.setAttribute("aria-pressed", String(group.has(chip.dataset.value)));
        });
        el.onlyNumbered.classList.toggle("is-on", state.onlyNumbered);
        el.onlyNumbered.setAttribute("aria-pressed", String(state.onlyNumbered));
        el.onlyFavorites.classList.toggle("is-on", state.onlyFavorites);
        el.onlyFavorites.setAttribute("aria-pressed", String(state.onlyFavorites));

        const activeCount = state.members.size + state.sections.size + state.categories.size + (state.onlyNumbered ? 1 : 0) + (state.onlyFavorites ? 1 : 0);
        el.filterCount.textContent = String(activeCount);
        el.filterCount.hidden = activeCount === 0;
    }

    function syncMachineButtons() {
        el.machineButtons.forEach((button) => {
            const active = button.dataset.machine === state.machine;
            button.classList.toggle("is-on", active);
            button.setAttribute("aria-pressed", String(active));
        });
    }

    /* ---------- 부를 곡 목록 ---------- */

    function setlistSongs() {
        return setlist.map((key) => songByKey.get(key)).filter(Boolean);
    }

    function renderSetlist() {
        const list = setlistSongs();
        el.setlistBar.hidden = list.length === 0;
        el.setlistCount.textContent = String(list.length);
        if (!list.length) {
            el.setlistPanel.hidden = true;
            el.setlistToggle.setAttribute("aria-expanded", "false");
            el.setlistItems.innerHTML = "";
            return;
        }
        el.setlistItems.innerHTML = list.map((song, index) => `<li class="setlist-item" data-key="${esc(song.key)}">
      <span class="setlist-name"><strong>${esc(song.title)}</strong><span>${esc(song.artist)}</span></span>
      <span class="setlist-numbers">${song.tj ? "TJ " + esc(song.tj) : ""}${song.tj && song.ky ? " · " : ""}${song.ky ? "금영 " + esc(song.ky) : ""}${!song.tj && !song.ky ? "번호 없음" : ""}</span>
      <span class="setlist-buttons">
        <button type="button" class="icon-btn" data-setlist-action="up" ${index === 0 ? "disabled" : ""} aria-label="위로">↑</button>
        <button type="button" class="icon-btn" data-setlist-action="down" ${index === list.length - 1 ? "disabled" : ""} aria-label="아래로">↓</button>
        <button type="button" class="icon-btn" data-setlist-action="remove" aria-label="빼기">×</button>
      </span>
    </li>`).join("");
    }

    function setlistText() {
        return setlistSongs().map((song, index) => {
            const numbers = [];
            if (song.tj && state.machine !== "ky") numbers.push("TJ " + song.tj);
            if (song.ky && state.machine !== "tj") numbers.push("금영 " + song.ky);
            return `${index + 1}. ${song.title} - ${song.artist}${numbers.length ? " (" + numbers.join(", ") + ")" : " (번호 없음)"}`;
        }).join("\n");
    }

    function saveSetlist() {
        writeStore(STORAGE_KEYS.setlist, setlist);
    }

    /* ---------- 클립보드·토스트 ---------- */

    let toastTimer = null;

    function showToast(message) {
        el.toast.textContent = message;
        el.toast.hidden = false;
        el.toast.classList.add("is-visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => {
            el.toast.classList.remove("is-visible");
            toastTimer = window.setTimeout(() => { el.toast.hidden = true; }, 200);
        }, 1800);
    }

    async function copyText(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            }
        } catch (error) {
            /* 아래 대체 방법으로 넘어간다. */
        }
        try {
            const helper = document.createElement("textarea");
            helper.value = text;
            helper.setAttribute("readonly", "");
            helper.style.position = "fixed";
            helper.style.opacity = "0";
            document.body.appendChild(helper);
            helper.select();
            const copied = document.execCommand("copy");
            document.body.removeChild(helper);
            return copied;
        } catch (error) {
            return false;
        }
    }

    function recordCopy() {
        try {
            window.Stelline.api("karaoke/record_copy", { method: "POST" }).catch(() => {});
        } catch (error) {
            /* 통계 실패는 무시한다. */
        }
    }

    /* ---------- 주소 표시줄 상태 ---------- */

    function syncUrl() {
        const params = new URLSearchParams();
        if (state.query) params.set("q", state.query);
        if (state.machine !== "both") params.set("machine", state.machine);
        if (state.sort !== "recent") params.set("sort", state.sort);
        if (state.members.size) params.set("member", Array.from(state.members).join("|"));
        if (state.sections.size) params.set("section", Array.from(state.sections).join("|"));
        if (state.categories.size) params.set("category", Array.from(state.categories).join("|"));
        if (state.onlyNumbered) params.set("numbered", "1");
        if (state.onlyFavorites) params.set("fav", "1");
        const query = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : ""));
    }

    function readUrlState() {
        const params = new URLSearchParams(window.location.search);
        if (params.get("q")) state.query = params.get("q");
        if (["tj", "ky", "both"].includes(params.get("machine"))) state.machine = params.get("machine");
        if (["recent", "title", "number"].includes(params.get("sort"))) state.sort = params.get("sort");
        (params.get("member") || "").split("|").filter(Boolean).forEach((value) => state.members.add(value));
        (params.get("section") || "").split("|").filter(Boolean).forEach((value) => state.sections.add(value));
        (params.get("category") || "").split("|").filter(Boolean).forEach((value) => state.categories.add(value));
        state.onlyNumbered = params.get("numbered") === "1";
        state.onlyFavorites = params.get("fav") === "1";
    }

    function applySharedSetlist() {
        const match = window.location.hash.match(/list=([0-9,]+)/);
        if (!match) return;
        const shared = match[1].split(",").map((value) => songById.get(Number(value))).filter(Boolean);
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
        if (!shared.length) {
            showToast("공유된 목록의 곡을 찾지 못했습니다.");
            return;
        }
        if (setlist.length && !window.confirm(`공유받은 ${shared.length}곡으로 부를 곡 목록을 바꿀까요? 지금 담아둔 목록은 사라집니다.`)) return;
        setlist = shared.map((song) => song.key);
        saveSetlist();
        renderSetlist();
        showToast(`공유받은 ${shared.length}곡을 불러왔습니다.`);
    }

    /* ---------- 데이터 ---------- */

    function ingest(payload) {
        songs = (payload.songs || []).map((song, index) => decorate(Object.assign({ sortOrder: index }, song)));
        members = payload.members || [];
        songByKey.clear();
        songById.clear();
        songs.forEach((song) => {
            songByKey.set(song.key, song);
            songById.set(song.id, song);
        });
        el.lastUpdated.textContent = payload.updatedAt ? `마지막 갱신: ${payload.updatedAt}` : "";
        // 저장해 둔 목록에서 지금은 사라진 곡은 정리한다.
        setlist = setlist.filter((key) => songByKey.has(key));
        renderChips();
        renderList();
        renderSetlist();
    }

    async function loadSongs() {
        const cached = readStore(STORAGE_KEYS.cache, null);
        if (cached && cached.songs) {
            usingCache = true;
            ingest(cached);
        }
        try {
            const response = await window.Stelline.api("karaoke/songs");
            if (!response.ok) throw new Error("목록을 불러오지 못했습니다.");
            const payload = await response.json();
            usingCache = false;
            el.offlineNote.hidden = true;
            writeStore(STORAGE_KEYS.cache, payload);
            ingest(payload);
            applySharedSetlist();
        } catch (error) {
            if (usingCache) {
                el.offlineNote.hidden = false;
                applySharedSetlist();
                return;
            }
            el.songList.innerHTML = '<p class="empty-state">목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</p>';
            el.resultCount.textContent = "";
        }
    }

    /* ---------- 제보 ---------- */

    function attachReportForm() {
        const toggle = document.getElementById("report-toggle");
        const panel = document.getElementById("report-panel");
        const form = document.getElementById("report-form");
        const content = document.getElementById("report-content");
        const status = document.getElementById("report-status");
        const captchaContainer = document.getElementById("report-captcha");
        let captchaWidget;
        if (!toggle || !panel || !form) return;

        toggle.addEventListener("click", () => {
            panel.hidden = !panel.hidden;
            toggle.textContent = panel.hidden ? "번호 제보" : "제보 입력 닫기";
            if (!panel.hidden) {
                content.focus();
                if (captchaContainer && window.turnstile && captchaWidget === undefined) {
                    captchaWidget = window.turnstile.render(captchaContainer, { sitekey: "0x4AAAAAAEgvGwCT4Q867aaL" });
                }
            }
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const value = content.value.trim();
            if (!value) return;
            const captchaToken = window.turnstile?.getResponse(captchaWidget);
            if (!captchaToken) {
                status.textContent = "캡차 인증을 완료하세요.";
                return;
            }
            status.textContent = "보내는 중...";
            try {
                const response = await window.Stelline.api("karaoke/reports", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content: value, captcha_token: captchaToken }),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "제보를 보내지 못했습니다.");
                form.reset();
                status.textContent = result.message;
                window.turnstile?.reset(captchaWidget);
            } catch (error) {
                status.textContent = error.message;
                window.turnstile?.reset(captchaWidget);
            }
        });
    }

    /* ---------- 랜덤 뽑기 ---------- */

    function showRandomPick() {
        if (!visibleSongs.length) return;
        const song = visibleSongs[Math.floor(Math.random() * visibleSongs.length)];
        el.pickTitle.textContent = song.title;
        el.pickArtist.textContent = song.artist;
        const numbers = [];
        if (song.tj) numbers.push({ label: "TJ", value: song.tj });
        if (song.ky) numbers.push({ label: "금영", value: song.ky });
        el.pickNumbers.innerHTML = numbers.length
            ? numbers.map((item) => `<button type="button" class="num-btn is-primary" data-action="copy" data-number="${esc(item.value)}" data-machine="${item.label === "TJ" ? "tj" : "ky"}"><span class="num-label">${item.label}</span><span class="num-value">${esc(item.value)}</span></button>`).join("")
            : '<p class="empty-state">아직 노래방 번호가 없는 곡이에요.<br>필터의 “번호 있는 곡만”을 켜면 부를 수 있는 곡만 뽑습니다.</p>';
        el.pickDialog.hidden = false;
    }

    /* ---------- 이벤트 ---------- */

    function bindEvents() {
        let searchTimer = null;
        el.searchInput.addEventListener("input", () => {
            el.searchClear.hidden = !el.searchInput.value;
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => {
                state.query = el.searchInput.value;
                renderList();
                syncUrl();
            }, 120);
        });
        el.searchClear.addEventListener("click", () => {
            el.searchInput.value = "";
            el.searchClear.hidden = true;
            state.query = "";
            el.searchInput.focus();
            renderList();
            syncUrl();
        });

        el.machineButtons.forEach((button) => {
            button.addEventListener("click", () => {
                state.machine = button.dataset.machine;
                writeStore(STORAGE_KEYS.machine, state.machine);
                syncMachineButtons();
                renderList();
                renderSetlist();
                syncUrl();
            });
        });

        el.sortSelect.addEventListener("change", () => {
            state.sort = el.sortSelect.value;
            renderList();
            syncUrl();
        });

        el.filterToggle.addEventListener("click", () => {
            el.filterPanel.hidden = !el.filterPanel.hidden;
            el.filterToggle.setAttribute("aria-expanded", String(!el.filterPanel.hidden));
        });

        el.filterPanel.addEventListener("click", (event) => {
            const chip = event.target.closest("[data-filter]");
            if (!chip) return;
            const group = chip.dataset.filter === "member" ? state.members : chip.dataset.filter === "section" ? state.sections : state.categories;
            if (group.has(chip.dataset.value)) group.delete(chip.dataset.value);
            else group.add(chip.dataset.value);
            syncChipStates();
            renderList();
            syncUrl();
        });

        el.onlyNumbered.addEventListener("click", () => {
            state.onlyNumbered = !state.onlyNumbered;
            syncChipStates();
            renderList();
            syncUrl();
        });
        el.onlyFavorites.addEventListener("click", () => {
            state.onlyFavorites = !state.onlyFavorites;
            syncChipStates();
            renderList();
            syncUrl();
        });
        el.filterReset.addEventListener("click", () => {
            state.members.clear();
            state.sections.clear();
            state.categories.clear();
            state.onlyNumbered = false;
            state.onlyFavorites = false;
            syncChipStates();
            renderList();
            syncUrl();
        });

        el.modeToggle.addEventListener("click", () => {
            const enabled = document.body.classList.toggle("karaoke-mode");
            el.modeToggle.setAttribute("aria-pressed", String(enabled));
            el.modeToggle.classList.toggle("is-on", enabled);
            writeStore(STORAGE_KEYS.mode, enabled);
        });

        el.songList.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-action]");
            if (!button) return;
            const card = button.closest(".song-card");
            const song = card ? songByKey.get(card.dataset.key) : null;

            if (button.dataset.action === "copy") {
                const copied = await copyText(button.dataset.number);
                showToast(copied
                    ? `${MACHINE_LABELS[button.dataset.machine]} ${button.dataset.number} 복사했어요`
                    : "복사하지 못했어요. 번호를 길게 눌러 복사해주세요.");
                if (copied) recordCopy();
                return;
            }
            if (!song) return;
            if (button.dataset.action === "favorite") {
                if (favorites.has(song.key)) favorites.delete(song.key);
                else favorites.add(song.key);
                writeStore(STORAGE_KEYS.favorites, Array.from(favorites));
                renderList();
                return;
            }
            if (button.dataset.action === "setlist") {
                const index = setlist.indexOf(song.key);
                if (index >= 0) setlist.splice(index, 1);
                else setlist.push(song.key);
                saveSetlist();
                renderList();
                renderSetlist();
                showToast(index >= 0 ? "목록에서 뺐어요" : "부를 곡 목록에 담았어요");
            }
        });

        el.setlistToggle.addEventListener("click", () => {
            el.setlistPanel.hidden = !el.setlistPanel.hidden;
            el.setlistToggle.setAttribute("aria-expanded", String(!el.setlistPanel.hidden));
            el.setlistToggle.classList.toggle("is-open", !el.setlistPanel.hidden);
        });

        el.setlistItems.addEventListener("click", (event) => {
            const button = event.target.closest("[data-setlist-action]");
            if (!button) return;
            const item = button.closest(".setlist-item");
            const index = setlist.indexOf(item.dataset.key);
            if (index < 0) return;
            const action = button.dataset.setlistAction;
            if (action === "remove") setlist.splice(index, 1);
            else if (action === "up" && index > 0) setlist.splice(index - 1, 0, setlist.splice(index, 1)[0]);
            else if (action === "down" && index < setlist.length - 1) setlist.splice(index + 1, 0, setlist.splice(index, 1)[0]);
            saveSetlist();
            renderSetlist();
            renderList();
        });

        el.setlistCopy.addEventListener("click", async () => {
            const copied = await copyText(setlistText());
            showToast(copied ? "목록을 복사했어요" : "복사하지 못했어요");
        });

        el.setlistShare.addEventListener("click", async () => {
            const ids = setlistSongs().map((song) => song.id).join(",");
            const link = `${window.location.origin}${window.location.pathname}#list=${ids}`;
            const copied = await copyText(link);
            showToast(copied ? "공유 링크를 복사했어요" : "복사하지 못했어요");
        });

        el.setlistClear.addEventListener("click", () => {
            if (!window.confirm("부를 곡 목록을 비울까요?")) return;
            setlist = [];
            saveSetlist();
            renderSetlist();
            renderList();
        });

        el.randomPick.addEventListener("click", showRandomPick);
        el.pickAgain.addEventListener("click", showRandomPick);
        el.pickClose.addEventListener("click", () => { el.pickDialog.hidden = true; });
        el.pickDialog.addEventListener("click", async (event) => {
            if (event.target === el.pickDialog) {
                el.pickDialog.hidden = true;
                return;
            }
            const button = event.target.closest('[data-action="copy"]');
            if (!button) return;
            const copied = await copyText(button.dataset.number);
            showToast(copied ? `${MACHINE_LABELS[button.dataset.machine]} ${button.dataset.number} 복사했어요` : "복사하지 못했어요");
            if (copied) recordCopy();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !el.pickDialog.hidden) el.pickDialog.hidden = true;
        });

        // 이미 이 화면을 보고 있을 때 공유 링크를 눌러도 목록이 바뀌도록 한다.
        window.addEventListener("hashchange", applySharedSetlist);
    }

    function cacheElements() {
        el.searchInput = document.getElementById("search-input");
        el.searchClear = document.getElementById("search-clear");
        el.machineButtons = Array.from(document.querySelectorAll(".machine-switch [data-machine]"));
        el.sortSelect = document.getElementById("sort-select");
        el.filterToggle = document.getElementById("filter-toggle");
        el.filterCount = document.getElementById("filter-count");
        el.filterPanel = document.getElementById("filter-panel");
        el.memberChips = document.getElementById("member-chips");
        el.sectionChips = document.getElementById("section-chips");
        el.categoryChips = document.getElementById("category-chips");
        el.onlyNumbered = document.getElementById("only-numbered");
        el.onlyFavorites = document.getElementById("only-favorites");
        el.filterReset = document.getElementById("filter-reset");
        el.modeToggle = document.getElementById("mode-toggle");
        el.resultCount = document.getElementById("result-count");
        el.randomPick = document.getElementById("random-pick");
        el.songList = document.getElementById("song-list");
        el.lastUpdated = document.getElementById("last-updated");
        el.offlineNote = document.getElementById("offline-note");
        el.setlistBar = document.getElementById("setlist-bar");
        el.setlistToggle = document.getElementById("setlist-toggle");
        el.setlistPanel = document.getElementById("setlist-panel");
        el.setlistItems = document.getElementById("setlist-items");
        el.setlistCount = document.getElementById("setlist-count");
        el.setlistCopy = document.getElementById("setlist-copy");
        el.setlistShare = document.getElementById("setlist-share");
        el.setlistClear = document.getElementById("setlist-clear");
        el.toast = document.getElementById("toast");
        el.pickDialog = document.getElementById("pick-dialog");
        el.pickTitle = document.getElementById("pick-title");
        el.pickArtist = document.getElementById("pick-artist");
        el.pickNumbers = document.getElementById("pick-numbers");
        el.pickAgain = document.getElementById("pick-again");
        el.pickClose = document.getElementById("pick-close");
    }

    function restorePreferences() {
        favorites = new Set(readStore(STORAGE_KEYS.favorites, []));
        setlist = readStore(STORAGE_KEYS.setlist, []).filter((key) => typeof key === "string");
        const savedMachine = readStore(STORAGE_KEYS.machine, "both");
        if (["tj", "ky", "both"].includes(savedMachine)) state.machine = savedMachine;
        readUrlState();

        el.searchInput.value = state.query;
        el.searchClear.hidden = !state.query;
        el.sortSelect.value = state.sort;
        syncMachineButtons();
        if (readStore(STORAGE_KEYS.mode, false) === true) {
            document.body.classList.add("karaoke-mode");
            el.modeToggle.classList.add("is-on");
            el.modeToggle.setAttribute("aria-pressed", "true");
        }
        const hasFilters = state.members.size || state.sections.size || state.categories.size || state.onlyNumbered || state.onlyFavorites;
        if (hasFilters) {
            el.filterPanel.hidden = false;
            el.filterToggle.setAttribute("aria-expanded", "true");
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        cacheElements();
        restorePreferences();
        bindEvents();
        attachReportForm();
        loadSongs();
    });
})();

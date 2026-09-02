/* 멤버·구분·종류·보기 옵션 필터.
 *
 * 멤버는 유닛으로 묶어 보여 준다. 유닛을 옮긴 멤버는 이전 유닛으로도 찾을 수 있게
 * 안내(title)만 남긴다. 구분은 실제로 쓰이는 값만 내보인다.
 */
import { CATEGORY_LABELS, SECTION_LABELS, SECTION_ORDER } from "./constants";

function Chip({ active, title, onClick, children }) {
  return (
    <button
      type="button"
      className={`kara-chip${active ? " is-on" : ""}`}
      aria-pressed={active}
      title={title}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function FilterPanel({ hidden, members, songs, filters, dispatch }) {
  const unitGroups = new Map();
  members.forEach((member) => {
    const unit = member.unit || "기타";
    if (!unitGroups.has(unit)) unitGroups.set(unit, []);
    unitGroups.get(unit).push(member);
  });

  const usedSections = SECTION_ORDER.filter((section) => songs.some((song) => song.section === section));

  return (
    <div id="filter-panel" className="kara-filters" hidden={hidden}>
      <div className="kara-filter-group is-wide">
        <h3>멤버</h3>
        <div id="member-chips" className="kara-chips">
          {Array.from(unitGroups.entries()).map(([unit, group]) => (
            <div className="kara-chip-row" key={unit}>
              <span className="kara-chip-unit">{unit}</span>
              {group.map((member) => {
                const formerUnits = member.formerUnits || [];
                return (
                  <Chip
                    key={member.name}
                    active={filters.members.has(member.name)}
                    title={formerUnits.length ? `${member.name} (구 ${formerUnits.join(" · ")})` : undefined}
                    onClick={() => dispatch({ type: "toggle", group: "members", value: member.name })}
                  >
                    {member.name}
                  </Chip>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="kara-filter-group">
        <h3>여러 개 고를 때</h3>
        <div id="match-switch" className="machine-switch" role="group" aria-label="여러 조건을 고를 때 찾는 방법">
          {[
            { value: "or", label: "하나라도" },
            { value: "and", label: "모두" },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              className={filters.filterMode === option.value ? "is-on" : undefined}
              aria-pressed={filters.filterMode === option.value}
              onClick={() => dispatch({ type: "set", key: "filterMode", value: option.value })}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="kara-filter-hint">
          멤버를 여러 명 고를 때 적용됩니다. 구분·종류는 곡마다 하나뿐이라 늘 “하나라도”로 찾습니다.
        </p>
      </div>

      <div className="kara-filter-group">
        <h3>구분</h3>
        <div id="section-chips" className="kara-chips">
          {usedSections.map((section) => (
            <Chip
              key={section}
              active={filters.sections.has(section)}
              onClick={() => dispatch({ type: "toggle", group: "sections", value: section })}
            >
              {SECTION_LABELS[section] || section}
            </Chip>
          ))}
        </div>
      </div>

      <div className="kara-filter-group">
        <h3>종류</h3>
        <div id="category-chips" className="kara-chips">
          {Object.keys(CATEGORY_LABELS).map((category) => (
            <Chip
              key={category}
              active={filters.categories.has(category)}
              onClick={() => dispatch({ type: "toggle", group: "categories", value: category })}
            >
              {CATEGORY_LABELS[category]}
            </Chip>
          ))}
        </div>
      </div>

      <div className="kara-filter-group">
        <h3>보기 옵션</h3>
        <div className="kara-chips">
          <Chip
            active={filters.onlyNumbered}
            onClick={() => dispatch({ type: "set", key: "onlyNumbered", value: !filters.onlyNumbered })}
          >
            번호 있는 곡만
          </Chip>
          <Chip
            active={filters.onlyFavorites}
            onClick={() => dispatch({ type: "set", key: "onlyFavorites", value: !filters.onlyFavorites })}
          >
            즐겨찾기만
          </Chip>
          <button type="button" className="kara-chip is-reset" onClick={() => dispatch({ type: "reset" })}>
            필터 초기화
          </button>
        </div>
      </div>
    </div>
  );
}

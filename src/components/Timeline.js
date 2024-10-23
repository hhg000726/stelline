// src/components/Timeline.js
import React, { useRef, useState, useEffect } from 'react';
import TimelineItem from './TimelineItem';
import './Timeline.css';
import events from './events.json';

const MEMBERS = ['칸나', '유니', '히나', '시로', '리제', '타비', '부키', '린', '나나', '리코', '단체, 서버'];

const COLORS = [
  '#373584',
  '#B77DE4',
  '#DFB387',
  '#757875',
  '#D94854',
  '#50D3F0',
  '#794EB7',
  '#77A0F2',
  '#FFAABA',
  '#7AD95F',
  '#222222',
];

// Timeline.js 파일에서 수정
const getGradientStyle = (members) => {
  const activeColors = members
    .map((value, index) => (value === 1 ? COLORS[index] : null))
    .filter(Boolean);

  if (activeColors.length === 0) {
    return { background: '#3498db' }; // 기본 색상 (남색)
  }

  const gradientPercentage = 100 / activeColors.length;
  const gradientColors = activeColors
    .map((color, index) => `${color} ${index * gradientPercentage}%, ${color} ${(index + 1) * gradientPercentage}%`)
    .join(', ');

  return {
    background: `linear-gradient(90deg, ${gradientColors})`,
  };
};


// Group events by date using reduce
const groupEventsByDate = (events) => {

  return events.reduce((grouped, event) => {
    if (!grouped[event.date]) {
      grouped[event.date] = [];
    }
    grouped[event.date].push(event);
    return grouped;
  }, {});
};

const Timeline = () => {
  const itemRefs = useRef({});
  let eventsCopy = [...events].sort((a, b) => new Date(a.date) - new Date(b.date));


  const [searchText, setSearchText] = useState('');
  const [selectedMembers, setSelectedMembers] = useState(Array(11).fill(0));  // 멤버 필터링용 상태
  const [expandedYears, setExpandedYears] = useState({});
  const [expandedMonths, setExpandedMonths] = useState({});
  const [visibleDates, setVisibleDates] = useState([]);
  const [filterOperation, setFilterOperation] = useState('AND');  // AND 또는 OR 선택
  const [navOpen, setNavOpen] = useState(false); // 내비게이션 열림 상태 관리

  // 제목과 멤버 필터링을 적용한 이벤트 목록
  const filteredevents = eventsCopy.filter((event) => {
    // 제목 검색 필터
    const titleMatch = event.title.includes(searchText);
    console.log(titleMatch, searchText)

    // 멤버 필터: 선택된 연산 방식에 따라 필터링
    let memberMatch;
    if (filterOperation === 'AND') {
      memberMatch = selectedMembers.every((isSelected, idx) =>
        !isSelected || event.members[idx] === 1
      );
    } else if (filterOperation === 'OR') {
      memberMatch = selectedMembers.some((isSelected, idx) =>
        isSelected && event.members[idx] === 1
      );
    }

    return titleMatch && memberMatch;
  });

  const groupedEvents = groupEventsByDate(filteredevents);

  // Group dates by year and month for navigation
  const groupedByYearMonth = filteredevents.reduce((grouped, event) => {
    const [year, month, day] = event.date.split('-');
    if (!grouped[year]) grouped[year] = {};
    if (!grouped[year][month]) grouped[year][month] = [];
    grouped[year][month].push(event);
    return grouped;
  }, {});


  // Lazy load items based on visibility
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisibleDates((prevDates) => {
              if (!prevDates.includes(entry.target.dataset.date)) {
                return [...prevDates, entry.target.dataset.date];
              }
              return prevDates;
            });
          }
        });
      },
      { threshold: 0 }
    );

    Object.values(itemRefs.current).forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => {
      Object.values(itemRefs.current).forEach((el) => {
        if (el) observer.unobserve(el);
      });
    };
  }, [itemRefs]);

  const handleNavClick = (arg) => {
    if (itemRefs.current[arg]) {
      itemRefs.current[arg].scrollIntoView({ behavior: 'auto' });
    }
  };

  // Toggle the expansion state for a year
  const toggleYear = (year) => {
    setExpandedYears((prev) => {
      // 모든 연도를 접기
      const newExpandedYears = Object.keys(prev).reduce((acc, key) => {
        acc[key] = false;
        return acc;
      }, {});
  
      // 클릭한 연도는 토글하여 펼치거나 접음
      newExpandedYears[year] = !prev[year];
  
      // 만약 연도를 접는 경우, 해당 연도에 속한 모든 월도 접기
      if (!newExpandedYears[year]) {
        const monthsInYear = Object.keys(groupedByYearMonth[year]);
        setExpandedMonths((prevMonths) => {
          const newExpandedMonths = { ...prevMonths };
          monthsInYear.forEach((month) => {
            newExpandedMonths[`${year}-${month}`] = false;
          });
          return newExpandedMonths;
        });
      }
  
      return newExpandedYears;
    });
  
    // 다른 연도를 접을 때 해당 연도의 모든 월도 접기
    setExpandedMonths((prev) => {
      const newExpandedMonths = { ...prev };
      Object.keys(groupedByYearMonth).forEach((otherYear) => {
        if (otherYear !== year) {
          Object.keys(groupedByYearMonth[otherYear]).forEach((month) => {
            newExpandedMonths[`${otherYear}-${month}`] = false;
          });
        }
      });
      return newExpandedMonths;
    });
  };

  // Toggle the expansion state for a month
  const toggleMonth = (year, month) => {
    setExpandedMonths((prev) => {
      // 같은 연도의 다른 모든 월을 접기
      const newExpandedMonths = { ...prev };
      Object.keys(groupedByYearMonth[year]).forEach((otherMonth) => {
        newExpandedMonths[`${year}-${otherMonth}`] = false;
      });
  
      // 클릭한 월의 상태를 반대로 토글
      newExpandedMonths[`${year}-${month}`] = !prev[`${year}-${month}`];
  
      return newExpandedMonths;
    });
  };

  const handleMemberChange = (index) => {
    const updatedMembers = [...selectedMembers];
    updatedMembers[index] = !updatedMembers[index];
    setSelectedMembers(updatedMembers);
  };

  const handleSearchChange = (e) => {
    setSearchText(e.target.value);
  };

  const handleResetFilters = () => {
    setSearchText('');
    setSelectedMembers(Array(11).fill(0));
  };

  const toggleNav = () => {
    setNavOpen((prevOpen) => !prevOpen);
  };

  return (
    <div className="timeline-page">

      <button className="nav-toggle-button" onClick={toggleNav}>
        {navOpen ? '내비게이션 닫기' : '내비게이션 열기'}
      </button>
      <div className={`timeline-nav ${navOpen ? 'open' : 'closed'}`}>

        <h2>내비게이션</h2>

        <input
          type="text"
          placeholder="제목 검색"
          value={searchText}
          onChange={handleSearchChange}
          style={{ width: '90%', padding: '5px', marginBottom: '10px' }}
        />

        <ul>
          {Object.keys(groupedByYearMonth).map((year) => (
            <li key={year}>
              <span onClick={() => toggleYear(year)} style={{ cursor: 'pointer', display: 'block' }}>
                {year} {expandedYears[year] ? '▲' : '▼'}
              </span>
              {expandedYears[year] && (
                <ul>
                  {Object.keys(groupedByYearMonth[year]).sort((a, b) => parseInt(a) - parseInt(b)).map((month) => (
                    <li key={month}>
                      <span onClick={() => toggleMonth(year, month)} style={{ cursor: 'pointer', display: 'block' }}>
                        {month}월 {expandedMonths[`${year}-${month}`] ? '▲' : '▼'}
                      </span>
                      {expandedMonths[`${year}-${month}`] && (
                        <ul>
                          {groupedByYearMonth[year][month].map((event, index) => {
                            return (
                              <li key={index} onClick={() => handleNavClick(event.date)} style={getGradientStyle(event.members)}>
                                {event.date.split('-')[2]}일 -
                                {event.title.split('\n').map((line, lineIndex) => (
                                  <React.Fragment key={lineIndex}>
                                    {line}
                                    <br />
                                  </React.Fragment>
                                ))}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>

        {/* 멤버 체크박스 */}
        <div style={{ marginTop: '20px' }}>
          <h4>멤버 필터</h4>


          <button onClick={handleResetFilters} style={{ marginBottom: '10px' }}>초기화</button>
          {MEMBERS.map((member, index) => (
            <label key={index} style={{ display: 'block', marginBottom: '1px' }}>
              <input
                type="checkbox"
                checked={selectedMembers[index]}
                onChange={() => handleMemberChange(index)}
              />{' '}
              {member}
            </label>
          ))}
          <div style={{ marginTop: '20px' }}>
            <h4>필터 방식</h4>
            <div>
              <label style={{ display: 'block' }}>
                <input
                  type="radio"
                  name="filterOperation"
                  value="AND"
                  checked={filterOperation === 'AND'}
                  onChange={() => setFilterOperation('AND')}
                />{' '}
                모두 포함
              </label>
              <label style={{ display: 'block' }}>
                <input
                  type="radio"
                  name="filterOperation"
                  value="OR"
                  checked={filterOperation === 'OR'}
                  onChange={() => setFilterOperation('OR')}
                />{' '}
                하나라도 포함
              </label>
            </div>

          </div>
        </div>

      </div>
      <div className="timeline-container">
        <h1>타임라인</h1>
        <div className="timeline">
          {Object.keys(groupedEvents).map((date, index) => (
            <div
              key={index}
              ref={(el) => (itemRefs.current[date] = el)}
              data-date={date}
            >
              {visibleDates.includes(date) && (
                <>
                  <h2>{date}</h2>
                  {groupedEvents[date].map((event, idx) => (
                    <TimelineItem
                      key={idx}
                      date={event.date}
                      title={event.title}
                      videoIds={event.videoIds}
                    />
                  ))}
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Timeline;
// src/components/TimelineItem.js
import React, { useEffect, useRef, useState } from 'react';
import './TimelineItem.css';

const TimelineItem = ({ title, videoIds, refCallback }) => {
  const itemRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0.1 }
    );

    if (itemRef.current) {
      observer.observe(itemRef.current);
    }

    if (refCallback) {
      refCallback(itemRef.current);
    }

    return () => {
      if (itemRef.current) {
        observer.unobserve(itemRef.current);
      }
    };
  }, [refCallback]);

  return (
    <div
      ref={itemRef}
    >
      <div className="timeline-content">
        <h2>
          {title.split('\n').map((line, index) => (
            <React.Fragment key={index}>
              {line}
              <br />
            </React.Fragment>
          ))}
        </h2>
        <div className="youtube-videos">
          {videoIds.map((videoId, idx) => (
            <div key={idx} className="youtube-video">
              <iframe
                loading="lazy"
                width="560"
                height="315"
                src={`https://www.youtube.com/embed/${videoId}`}
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                title={`${title} - Video ${idx + 1}`}
              ></iframe>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default TimelineItem;

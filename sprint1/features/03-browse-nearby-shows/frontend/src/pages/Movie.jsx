import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getShows, getShow, groupByEvent, fmtDuration, fmtTime, dayKey, money } from '../api.js';
import { useApp } from '../store.jsx';
import { Back, Poster, Loading, ErrorMsg } from '../ui.jsx';

export default function Movie() {
  const { eventId } = useParams();
  const { city } = useApp();
  const [group, setGroup] = useState(null);
  const [desc, setDesc] = useState('');
  const [day, setDay] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    getShows({ city }).then((p) => {
      const g = groupByEvent(p.items).find((x) => x.event.id === eventId);
      if (!g) return setErr('This event is no longer available');
      setGroup(g); setDay(dayKey(g.shows[0].start_time));
      getShow(g.shows[0].id).then((d) => setDesc(d.event.description || ''));
    }).catch((e) => setErr(e.message));
  }, [eventId, city]);

  const days = useMemo(() => [...new Set((group?.shows || []).map((s) => dayKey(s.start_time)))], [group]);
  const byVenue = useMemo(() => {
    const m = new Map();
    (group?.shows || []).filter((s) => dayKey(s.start_time) === day).forEach((s) => {
      m.set(s.venue.id, { venue: s.venue, shows: [...(m.get(s.venue.id)?.shows || []), s] });
    });
    return [...m.values()];
  }, [group, day]);

  if (err) return <main className="screen"><Back /><ErrorMsg msg={err} /></main>;
  if (!group) return <main className="screen"><Back /><Loading /></main>;
  const e = group.event;

  return (
    <main className="screen no-pad">
      <div className="hero">
        <Poster event={e} className="hero-img" /><div className="hero-fade" />
        <div className="hero-top"><Back /></div>
        <div className="hero-body">
          <p className="muted sm">{[e.genre, e.event_type[0] + e.event_type.slice(1).toLowerCase(), fmtDuration(e.duration_minutes)].filter(Boolean).join(' • ')}</p>
          <h1>{e.title}</h1>
          <div className="row gap"><span className="tag">{e.event_type}</span>{e.language && <span className="tag">{e.language.slice(0, 3).toUpperCase()}</span>}</div>
        </div>
      </div>
      <div className="stats">
        <div><b>{e.language || '—'}</b><span>Language</span></div>
        <div><b>{fmtDuration(e.duration_minutes) || '—'}</b><span>Duration</span></div>
        <div><b>{group.minPrice != null ? money(group.minPrice) : '—'}</b><span>Tickets from</span></div>
      </div>
      <div className="pad-x">
        <a className="btn" href="#showtimes">Buy tickets</a>
        <h3 className="mt">Synopsis</h3>
        <p className="syn">{desc || 'No synopsis available yet.'}</p>
        <h3 className="mt" id="showtimes">Showtimes</h3>
        <div className="chips">
          {days.map((d) => (
            <button key={d} className={`pill ${d === day ? 'on' : ''}`} onClick={() => setDay(d)}>
              {new Date(d + 'T00:00').toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short' })}
            </button>
          ))}
        </div>
        {byVenue.map(({ venue, shows }) => (
          <div className="venue" key={venue.id}>
            <b>{venue.name}</b><span className="muted sm">{venue.address}, {venue.city}</span>
            <div className="times">
              {shows.map((s) => s.is_sold_out
                ? <span key={s.id} className="time off">{fmtTime(s.start_time)}<small>Sold out</small></span>
                : <Link key={s.id} to={`/seats/${s.id}`} className="time">{fmtTime(s.start_time)}<small>from {money(s.min_price)}</small></Link>)}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

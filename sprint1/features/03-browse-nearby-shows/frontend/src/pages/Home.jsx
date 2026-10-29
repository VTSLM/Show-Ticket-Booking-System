import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { getShows, searchShows, getCities, groupByEvent, fmtDuration } from '../api.js';
import { useApp } from '../store.jsx';
import { Poster, Search, Loading, ErrorMsg } from '../ui.jsx';

function CityPicker({ onPick, onClose }) {
  const [q, setQ] = useState('');
  const [cities, setCities] = useState([]);
  useEffect(() => { getCities(q).then(setCities).catch(() => setCities([])); }, [q]);
  return (
    <div className="sheet-wrap" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        <h3>Select your city</h3>
        <input className="field" autoFocus placeholder="Search city" value={q} onChange={(e) => setQ(e.target.value)} />
        <ul className="list">
          {cities.map((c) => (
            <li key={c.city + c.state}><button onClick={() => onPick(c.city)}>
              <b>{c.city}</b><span className="muted">{c.state} · {c.show_count} shows</span></button></li>
          ))}
          {!cities.length && <li className="muted pad">No cities with upcoming shows.</li>}
        </ul>
      </div>
    </div>
  );
}

function Rail({ title, groups }) {
  if (!groups.length) return null;
  return (
    <section>
      <div className="sec-head"><h2>{title}</h2></div>
      <div className="rail">
        {groups.map((g) => (
          <Link to={`/movie/${g.event.id}`} key={g.event.id} className="card">
            <Poster event={g.event} />
            <h4>{g.event.title}</h4>
            <p className="muted">{[g.event.language, fmtDuration(g.event.duration_minutes)].filter(Boolean).join(' • ')}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function Home() {
  const { city, setCity } = useApp();
  const [pickCity, setPickCity] = useState(!city);
  const [searching, setSearching] = useState(false);
  const [q, setQ] = useState('');
  const [genre, setGenre] = useState('All');
  const [groups, setGroups] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!city) return;
    setGroups(null); setErr('');
    const t = setTimeout(() => {
      const req = q.trim() ? searchShows({ q: q.trim(), city }) : getShows({ city });
      req.then((p) => setGroups(groupByEvent(p.items))).catch((e) => setErr(e.message));
    }, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [city, q]);

  const genres = useMemo(() => ['All', ...new Set((groups || []).map((g) => g.event.genre).filter(Boolean))], [groups]);
  const shown = (groups || []).filter((g) => genre === 'All' || g.event.genre === genre);
  const movies = shown.filter((g) => g.event.event_type === 'MOVIE');
  const live = shown.filter((g) => g.event.event_type !== 'MOVIE');

  return (
    <main className="screen">
      <header className="top">
        <h1>Movies</h1>
        <div className="row gap">
          <button className="pill sm" onClick={() => setPickCity(true)}>📍 {city || 'Select city'}</button>
          <button className="icon-btn" aria-label="Search" onClick={() => { setSearching(!searching); setQ(''); }}><Search /></button>
        </div>
      </header>
      {searching && <input className="field" autoFocus placeholder="Search movies & events" value={q} onChange={(e) => setQ(e.target.value)} />}
      <div className="chips">
        {genres.map((g) => <button key={g} className={`pill ${g === genre ? 'on' : ''}`} onClick={() => setGenre(g)}>{g}</button>)}
      </div>
      {err && <ErrorMsg msg={err} />}
      {!err && groups === null && city && <Loading />}
      {groups && !shown.length && <p className="muted center pad">{q ? `Nothing found for “${q}”.` : `No upcoming shows in ${city}.`}</p>}
      <Rail title="Now showing" groups={movies} />
      <Rail title="Live & comedy" groups={live} />
      {pickCity && <CityPicker onClose={() => city && setPickCity(false)} onPick={(c) => { setCity(c); setPickCity(false); }} />}
    </main>
  );
}

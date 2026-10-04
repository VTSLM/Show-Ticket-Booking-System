import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getShow, fmtDate, fmtTime, money } from '../api.js';
import { useApp } from '../store.jsx';
import { Back, Loading, ErrorMsg } from '../ui.jsx';

const ROWS = 'ABCDEFGHIJ'.split('');
const COLS = 10;
const MAX = 8;
const hash = (s) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);

export default function Seats() {
  const { showId } = useParams();
  const nav = useNavigate();
  const { setBooking } = useApp();
  const [show, setShow] = useState(null);
  const [err, setErr] = useState('');
  const [picked, setPicked] = useState([]);
  const [ask, setAsk] = useState(false);

  useEffect(() => { getShow(showId).then(setShow).catch((e) => setErr(e.message)); }, [showId]);

  // The backend has no per-seat endpoint yet, so the grid is generated from the real
  // seat categories (price) and real availability ratio. Swap this for an API call later.
  const seats = useMemo(() => {
    if (!show) return [];
    const cats = [...show.seat_categories].sort((a, b) => a.min_price - b.min_price);
    const takenPct = show.total_seats ? 1 - show.available_seats / show.total_seats : 0;
    return ROWS.flatMap((r, ri) => {
      const cat = cats[Math.min(cats.length - 1, Math.floor((ri * cats.length) / ROWS.length))];
      return Array.from({ length: COLS }, (_, i) => {
        const id = `${r}${i + 1}`;
        return { id, row: r, n: i + 1, type: cat?.seat_type, price: +cat?.min_price, taken: (hash(showId + id) % 1000) / 1000 < takenPct };
      });
    });
  }, [show, showId]);

  if (err) return <main className="screen"><Back /><ErrorMsg msg={err} /></main>;
  if (!show) return <main className="screen"><Back /><Loading /></main>;

  const chosen = seats.filter((s) => picked.includes(s.id));
  const total = chosen.reduce((a, s) => a + s.price, 0);
  const toggle = (s) => { if (s.taken) return; setPicked((p) => p.includes(s.id) ? p.filter((x) => x !== s.id) : p.length < MAX ? [...p, s.id] : p); };
  const go = (snacks) => { setBooking({ show, seats: chosen, snacks: {} }); nav(snacks ? '/snacks' : '/checkout'); };

  return (
    <main className="screen seat-screen">
      <header className="top center-title"><Back /><h3>Seat selection</h3><span style={{ width: 36 }} /></header>
      <h1 className="ttl">{show.event.title}</h1>
      <div className="row gap"><span className="tag">{show.event.event_type}</span>{show.event.language && <span className="tag">{show.event.language.slice(0, 3).toUpperCase()}</span>}<span className="muted sm">{show.screen_name}</span></div>
      <div className="meta3">
        <div><span>Cinema</span><b>{show.venue.name}</b></div>
        <div><span>Date</span><b>{fmtDate(show.start_time)}</b></div>
        <div><span>Time</span><b>{fmtTime(show.start_time)}</b></div>
      </div>
      <div className="screen-curve" />
      <div className="grid">
        {ROWS.map((r) => (
          <div className="seat-row" key={r}>
            <i>{r}</i>
            {seats.filter((s) => s.row === r).map((s) => (
              <button key={s.id} aria-label={`${s.id} ${s.type} ${money(s.price)}`} disabled={s.taken}
                className={`seat ${s.taken ? 'taken' : picked.includes(s.id) ? 'sel' : 'free'} ${s.n === 3 || s.n === 7 ? 'gap' : ''}`}
                onClick={() => toggle(s)} />
            ))}
            <i>{r}</i>
          </div>
        ))}
      </div>
      <div className="legend"><span><u className="seat sel" />Selected</span><span><u className="seat free" />Available</span><span><u className="seat taken" />Taken</span></div>
      <div className="cats">{show.seat_categories.map((c) => <span key={c.seat_type}>{c.seat_type[0] + c.seat_type.slice(1).toLowerCase()} {money(c.min_price)}</span>)}</div>
      <div className="dock">
        <button className="btn" disabled={!picked.length} onClick={() => setAsk(true)}>
          Proceed to checkout
          <small>{picked.length ? `${picked.join(', ')} | Total price: ${money(total)}` : 'Select up to 8 seats'}</small>
        </button>
      </div>
      {ask && (
        <div className="sheet-wrap" onClick={() => setAsk(false)}>
          <div className="sheet center" onClick={(e) => e.stopPropagation()}>
            <div className="grab" /><div className="bubble">🍿</div>
            <h3>Buy snacks in advance</h3>
            <p className="muted">Order a popcorn or a drink in advance together with the ticket!</p>
            <button className="btn" onClick={() => go(true)}>Buy snacks</button>
            <button className="link" onClick={() => go(false)}>Skip for now</button>
          </div>
        </div>
      )}
    </main>
  );
}

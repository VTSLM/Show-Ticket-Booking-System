import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApp } from '../store.jsx';
import { Back } from '../ui.jsx';
import { MENU } from './Snacks.jsx';
import { fmtDate, fmtTime, money } from '../api.js';

export default function Checkout() {
  const { booking, setBooking } = useApp();
  const nav = useNavigate();
  const [paid, setPaid] = useState(null);
  const { show, seats, snacks } = booking;
  if (!show) { nav('/', { replace: true }); return null; }
  const items = MENU.filter((m) => snacks[m.id]);
  const seatTotal = seats.reduce((a, s) => a + s.price, 0);
  const snackTotal = items.reduce((a, m) => a + m.price * snacks[m.id], 0);

  if (paid) return (
    <main className="screen center-all">
      <div className="bubble">✓</div><h2>Booking confirmed</h2>
      <p className="muted">{show.event.title} · {fmtDate(show.start_time)} · {fmtTime(show.start_time)}</p>
      <p className="muted">Seats {seats.map((s) => s.id).join(', ')}</p>
      <p className="ref">{paid}</p>
      <Link to="/" className="btn" onClick={() => setBooking({ show: null, seats: [], snacks: {} })}>Back to movies</Link>
    </main>
  );
  return (
    <main className="screen">
      <header className="top center-title"><Back /><h3>Checkout</h3><span style={{ width: 36 }} /></header>
      <h1 className="ttl">{show.event.title}</h1>
      <p className="muted">{show.venue.name} · {show.screen_name}</p>
      <p className="muted">{fmtDate(show.start_time)} · {fmtTime(show.start_time)}</p>
      <div className="bill">
        {seats.map((s) => <div key={s.id}><span>Seat {s.id} <small className="muted">{s.type.toLowerCase()}</small></span><b>{money(s.price)}</b></div>)}
        {items.map((m) => <div key={m.id}><span>{m.name} × {snacks[m.id]}</span><b>{money(m.price * snacks[m.id])}</b></div>)}
        <div className="total"><span>Total</span><b>{money(seatTotal + snackTotal)}</b></div>
      </div>
      <p className="muted sm">Payment is simulated — the backend has no booking or payment endpoints yet.</p>
      <div className="dock"><button className="btn" onClick={() => setPaid('BMS' + Date.now().toString(36).toUpperCase())}>Pay {money(seatTotal + snackTotal)}</button></div>
    </main>
  );
}

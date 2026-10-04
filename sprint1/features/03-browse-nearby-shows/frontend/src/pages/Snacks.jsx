import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../store.jsx';
import { Back, Search } from '../ui.jsx';
import { money } from '../api.js';

// Backend has no snacks catalogue yet — static menu.
export const MENU = [
  { id: 'pop', name: 'Plain popcorn L', price: 220, cat: 'Popcorn', icon: '🍿' },
  { id: 'cara', name: 'Caramel popcorn M', price: 260, cat: 'Popcorn', icon: '🍿' },
  { id: 'dog', name: "Cinema's hot dog", price: 180, cat: 'Popular', icon: '🌭' },
  { id: 'nach', name: 'Nachos with cheese', price: 200, cat: 'Popular', icon: '🧀' },
  { id: 'fries', name: 'French fries', price: 150, cat: 'Popular', icon: '🍟' },
  { id: 'cola', name: 'Coca-Cola Zero', price: 120, cat: 'Drinks', icon: '🥤' },
  { id: 'water', name: 'Mineral water', price: 50, cat: 'Drinks', icon: '💧' },
];
const CATS = ['Popular', 'Popcorn', 'Drinks'];

export default function Snacks() {
  const { booking, setBooking } = useApp();
  const nav = useNavigate();
  const [cat, setCat] = useState('Popular');
  const [qty, setQty] = useState(booking.snacks || {});
  const set = (id, d) => setQty((q) => ({ ...q, [id]: Math.max(0, (q[id] || 0) + d) }));
  const n = Object.values(qty).reduce((a, b) => a + b, 0);
  const sum = MENU.reduce((a, m) => a + (qty[m.id] || 0) * m.price, 0);
  if (!booking.show) { nav('/', { replace: true }); return null; }
  return (
    <main className="screen">
      <header className="top center-title"><Back /><h3>Snacks</h3><Search /></header>
      <div className="chips">{CATS.map((c) => <button key={c} className={`pill ${c === cat ? 'solid' : ''}`} onClick={() => setCat(c)}>{c}</button>)}</div>
      <ul className="snacks">
        {MENU.filter((m) => m.cat === cat).map((m) => (
          <li key={m.id}>
            <span className="bubble sm">{m.icon}</span>
            <div><b>{m.name}</b><span className="muted sm">{money(m.price)}</span></div>
            <div className="qty"><button onClick={() => set(m.id, -1)}>−</button><span>{qty[m.id] || 0}</span><button onClick={() => set(m.id, 1)}>+</button></div>
          </li>
        ))}
      </ul>
      <div className="dock">
        <button className="btn" onClick={() => { setBooking({ ...booking, snacks: qty }); nav('/checkout'); }}>
          Continue to checkout<small>{n ? `${n} item${n > 1 ? 's' : ''} | ${money(sum)}` : 'No snacks added'}</small>
        </button>
      </div>
    </main>
  );
}

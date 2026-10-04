import { useNavigate } from 'react-router-dom';
export const Back = ({ light }) => {
  const nav = useNavigate();
  return <button className="icon-btn" aria-label="Back" onClick={() => nav(-1)}>‹</button>;
};
export const Search = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
);
const hues = [220, 350, 150, 30, 270, 190];
export function Poster({ event, className = '' }) {
  if (event.poster_url) return <img className={`poster ${className}`} src={event.poster_url} alt={event.title} />;
  const h = hues[[...event.title].reduce((a, c) => a + c.charCodeAt(0), 0) % hues.length];
  return (
    <div className={`poster ph ${className}`} style={{ background: `linear-gradient(160deg, hsl(${h} 70% 38%), hsl(${(h + 40) % 360} 60% 14%))` }}>
      <span>{event.title}</span>
    </div>
  );
}
export const Loading = () => <p className="muted center pad">Loading…</p>;
export const ErrorMsg = ({ msg }) => <p className="error pad">{msg} — check that the backend is running.</p>;

import { Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home.jsx';
import Movie from './pages/Movie.jsx';
import Seats from './pages/Seats.jsx';
import Snacks from './pages/Snacks.jsx';
import Checkout from './pages/Checkout.jsx';

export default function App() {
  return (
    <div className="phone">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/movie/:eventId" element={<Movie />} />
        <Route path="/seats/:showId" element={<Seats />} />
        <Route path="/snacks" element={<Snacks />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </div>
  );
}

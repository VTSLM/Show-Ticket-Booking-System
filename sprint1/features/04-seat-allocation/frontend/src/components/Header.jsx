/**
 * Header.jsx — Site header with logo and navigation
 */

export function Header({ currentPage, onNavigate }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a
          href="#"
          className="logo"
          onClick={(e) => { e.preventDefault(); onNavigate('home'); }}
        >
          <div className="logo-icon">🎭</div>
          <span className="logo-text">SeatSelect</span>
        </a>

        <nav className="header-nav">
          <button
            className={`btn btn-secondary btn-sm ${currentPage === 'seat-map' ? 'text-brand' : ''}`}
            onClick={() => onNavigate('seat-map')}
            style={{ width: 'auto' }}
          >
            Book Tickets
          </button>
          <button
            className={`btn btn-secondary btn-sm ${currentPage === 'bookings' ? 'text-brand' : ''}`}
            onClick={() => onNavigate('bookings')}
            style={{ width: 'auto' }}
          >
            My Bookings
          </button>
        </nav>
      </div>
    </header>
  );
}

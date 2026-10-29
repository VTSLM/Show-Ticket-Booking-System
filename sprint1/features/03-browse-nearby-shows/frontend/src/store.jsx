import { createContext, useContext, useState, useEffect } from 'react';
const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function AppProvider({ children }) {
  const [city, setCityState] = useState(() => localStorage.getItem('city') || '');
  const [booking, setBooking] = useState({ show: null, seats: [], snacks: {} });
  useEffect(() => { city && localStorage.setItem('city', city); }, [city]);
  return <Ctx.Provider value={{ city, setCity: setCityState, booking, setBooking }}>{children}</Ctx.Provider>;
}

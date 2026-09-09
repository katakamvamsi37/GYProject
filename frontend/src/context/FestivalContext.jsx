import { createContext, useContext, useState } from 'react';
const FestivalContext = createContext(null);
export function FestivalProvider({ children }) {
  const [year, setYear] = useState(new Date().getFullYear());
  return <FestivalContext.Provider value={{ year, setYear }}>{children}</FestivalContext.Provider>;
}
export const useFestival = () => useContext(FestivalContext);

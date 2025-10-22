/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
  type JSX,
} from "react";

type SearchHandler = ((term: string) => void) | null;

interface SearchContextValue {
  value: string;
  setValue: (term: string) => void;
  register: (handler: SearchHandler) => void;
  clearHandler: (handler: SearchHandler) => void;
}

const SearchContext = createContext<SearchContextValue | undefined>(undefined);

export function SearchProvider({ children }: PropsWithChildren): JSX.Element {
  const [value, setValueState] = useState("");
  const handlers = useRef<Set<SearchHandler>>(new Set());

  const setValue = useCallback((term: string) => {
    setValueState(term);
    handlers.current.forEach((handler) => {
      handler?.(term);
    });
  }, []);

  const register = useCallback((handler: SearchHandler) => {
    if (!handler) return;
    handlers.current.add(handler);
  }, []);

  const clearHandler = useCallback((handler: SearchHandler) => {
    handlers.current.delete(handler);
  }, []);

  const valueObj = useMemo(
    () => ({
      value,
      setValue,
      register,
      clearHandler,
    }),
    [value, setValue, register, clearHandler]
  );

  return (
    <SearchContext.Provider value={valueObj}>
      {children}
    </SearchContext.Provider>
  );
}

export function useSearch(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) {
    throw new Error("useSearch must be used within a SearchProvider");
  }
  return ctx;
}

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

interface TokenContextValue {
  token: string;
  setToken: (value: string) => void;
  clearToken: () => void;
}

const TokenContext = createContext<TokenContextValue | undefined>(undefined);

const STORAGE_KEY = "beeline-admin-token";

export function TokenProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEY) || "");

  useEffect(() => {
    if (token) {
      localStorage.setItem(STORAGE_KEY, token);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [token]);

  const value = useMemo<TokenContextValue>(
    () => ({ token, setToken, clearToken: () => setToken("") }),
    [token]
  );

  return <TokenContext.Provider value={value}>{children}</TokenContext.Provider>;
}

export function useToken() {
  const ctx = useContext(TokenContext);
  if (!ctx) {
    throw new Error("useToken must be used within a TokenProvider");
  }
  return ctx;
}

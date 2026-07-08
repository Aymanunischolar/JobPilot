import { useCallback, useState } from "react";
import { verifyAdminCredentials } from "../api/client";

const STORAGE_KEY = "jobpilot-admin-auth";

interface Credentials {
  username: string;
  password: string;
}

function load(): Credentials | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Credentials) : null;
}

export function useAdminAuth() {
  const [credentials, setCredentials] = useState<Credentials | null>(load);

  const login = useCallback(async (username: string, password: string) => {
    await verifyAdminCredentials(username, password);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ username, password }));
    setCredentials({ username, password });
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setCredentials(null);
  }, []);

  return { credentials, isAuthenticated: credentials !== null, login, logout };
}

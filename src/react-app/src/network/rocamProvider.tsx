import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { ApiClient, type StatusResponse } from "./api";

interface RocamContextType {
  apiClient: ApiClient | null;
  error: Error | null;
  status: StatusResponse | null;
}

const RocamContext = createContext<RocamContextType | undefined>(undefined);

interface RocamProviderProps {
  children: ReactNode;
}

export function RocamProvider({ children }: RocamProviderProps) {
  const [apiClient, setApiClient] = useState<ApiClient | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);

  // Initialize API client
  useEffect(() => {
    let isMounted = true;

    async function initializeApiClient() {
      try {
        setError(null);
        const client = await ApiClient.createAutomatic();

        if (isMounted) {
          setApiClient(client);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      }
    }

    initializeApiClient();

    return () => {
      isMounted = false;
    };
  }, []);

  // Poll status at 30Hz (or slower if limited by network)
  useEffect(() => {
    if (!apiClient) return;

    let isMounted = true;
    let timeoutId: number | null = null;
    const targetInterval = 1000 / 30; // 15Hz

    async function pollStatus() {
      if (!isMounted || !apiClient) return;

      const startTime = Date.now();

      try {
        const statusData = await apiClient.getStatus();

        if (isMounted) {
          setStatus(statusData);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      }

      if (!isMounted) return;

      // Calculate delay: wait for target interval, but account for request time
      // This ensures we poll at 30Hz when network is fast, or slower if network is slow
      const elapsed = Date.now() - startTime;
      const delay = Math.max(0, targetInterval - elapsed);

      timeoutId = window.setTimeout(pollStatus, delay);
    }

    // Start polling
    pollStatus();

    return () => {
      isMounted = false;
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [apiClient]);

  const value: RocamContextType = {
    apiClient,
    error,
    status,
  };

  return (
    <RocamContext.Provider value={value}>{children}</RocamContext.Provider>
  );
}

/**
 * Hook to access the API client from the Rocam context
 * @returns The API client, loading state, error state, and current status
 * @throws Error if used outside of RocamProvider
 */
export function useRocam() {
  const context = useContext(RocamContext);

  if (context === undefined) {
    throw new Error("useRocam must be used within a RocamProvider");
  }

  return context;
}

import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Prevent hidden tabs from continuously polling expensive backend endpoints.
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,
      staleTime: 0, // Ensure queries are treated as stale when mounting so user data is fresh per session
      retry: 1,
    },
  },
});

export function clearAppCache(): void {
  try {
    queryClient.clear();
  } catch (e) {
    console.warn("Failed to clear QueryClient cache", e);
  }
}

import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/errors";

/** Shared React Query client. Auth errors are not retried (the HttpClient
 * already performs one refresh+retry and signs out on failure); other errors
 * retry at most twice with backoff. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) => {
          if (error instanceof ApiError && (error.isAuthError || error.isValidationError)) return false;
          return failureCount < 2;
        },
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

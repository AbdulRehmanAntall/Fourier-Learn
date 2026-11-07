// For a request the page must not wait on (a check answer, docs/frontend.md §6.8): the caller
// gets the first attempt's result at once, and if that fails, further attempts carry on behind
// it, even after the component that made the request has gone.

type Options = {
  retries?: number;
  delayMs?: number;
  /** Whether trying again could help. Answers like 404 or 422 won't change. */
  retryable?: (error: unknown) => boolean;
  wait?: (ms: number) => Promise<void>;
};

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function retryInBackground<T>(
  attempt: () => Promise<T>,
  { retries = 3, delayMs = 1000, retryable = () => true, wait = sleep }: Options = {},
): Promise<T> {
  const first = attempt();
  first.catch(async (error: unknown) => {
    let last = error;
    for (let i = 1; i <= retries && retryable(last); i++) {
      await wait(delayMs * i);
      try {
        await attempt();
        return;
      } catch (next) {
        last = next;
      }
    }
  });
  return first;
}

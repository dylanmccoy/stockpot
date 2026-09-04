import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { cookLogsApi } from "../api/cookLogs";
import { Button, CookLogRow } from "../components";
import type { CookLogRead } from "../types";
import styles from "./History.module.css";

// Global household activity log (spec §10.8): every cook across all recipes,
// newest first, paged in on demand with a running "showing X of total". Each
// row is the shared `CookLogRow`, here with the recipe title shown and linked.
// Forward-only — no undo affordance (R-12).
//
// Paging keeps the spec's exact `["cook-logs", { limit, offset }]` query key
// (not `useInfiniteQuery`, whose key omits `offset`): one `useQuery` per
// offset, and every page fetched so far is retained in `pages` and shown in
// offset order. `total` and "load more" are driven by the current (latest)
// page's response.

const PAGE_SIZE = 50; // spec §10.8 / §5: `limit=50`

export default function History() {
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["cook-logs", { limit: PAGE_SIZE, offset }],
    queryFn: () => cookLogsApi.list({ limit: PAGE_SIZE, offset }),
    // Keep the current rows on screen while the next page loads.
    placeholderData: keepPreviousData,
  });

  // Retain each page keyed by its own `offset`, so a background refetch
  // replaces that page in place instead of duplicating it.
  const [pages, setPages] = useState<Record<number, CookLogRead[]>>({});
  useEffect(() => {
    const data = query.data;
    if (data) setPages((prev) => ({ ...prev, [data.offset]: data.items }));
  }, [query.data]);

  const logs = Object.keys(pages)
    .map(Number)
    .sort((a, b) => a - b)
    .flatMap((o) => pages[o]);

  const total = query.data?.total ?? 0;
  const hasMore = logs.length < total;
  // True only while the page for the *current* `offset` is still loading — not
  // for a background refetch of an already-loaded page.
  const fetchingNext = query.isFetching && query.data?.offset !== offset;

  return (
    <section className={styles.page} aria-busy={query.isFetching || undefined}>
      <header className={styles.head}>
        <h1>History</h1>
      </header>

      {query.isPending && (
        <p role="status" className={styles.muted}>
          Loading history…
        </p>
      )}

      {query.isError && logs.length === 0 && (
        <div className={styles.errorPanel} role="alert">
          <p>
            {query.error instanceof Error
              ? query.error.message
              : "Couldn’t load history."}
          </p>
          <Button variant="secondary" onClick={() => query.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {query.data && logs.length === 0 && (
        <div className={styles.empty}>
          <p>No cooks logged yet.</p>
          <Link to="/" className={styles.cta}>
            Browse recipes
          </Link>
        </div>
      )}

      {logs.length > 0 && (
        <>
          <p className={styles.count} role="status">
            Showing {logs.length} of {total}
          </p>

          <ul className={styles.feed}>
            {logs.map((log) => (
              <CookLogRow key={log.id} log={log} showRecipeTitle />
            ))}
          </ul>

          {query.isError ? (
            // A later page failed — offer a real retry of that same offset.
            <div className={styles.errorPanel} role="alert">
              <p>
                {query.error instanceof Error
                  ? query.error.message
                  : "Couldn’t load more."}
              </p>
              <Button variant="secondary" onClick={() => query.refetch()}>
                Retry
              </Button>
            </div>
          ) : (
            hasMore && (
              <Button
                variant="secondary"
                loading={fetchingNext}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Load more
              </Button>
            )
          )}
        </>
      )}
    </section>
  );
}

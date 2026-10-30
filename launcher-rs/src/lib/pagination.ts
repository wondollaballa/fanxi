import { useEffect, useMemo, useState } from "react";

/** The rows-per-page choices offered under every paginated table. */
export const TABLE_PAGE_SIZES = [10, 20, 50, 100] as const;

export type TablePageSize = (typeof TABLE_PAGE_SIZES)[number];

export const DEFAULT_TABLE_PAGE_SIZE: TablePageSize = 20;

/** The saved size for one table, or the 20-row default when nothing valid is stored. */
export function storedTablePageSize(storageKey: string): TablePageSize {
  try {
    const value = Number(window.localStorage.getItem(storageKey));
    return TABLE_PAGE_SIZES.find((size) => size === value) ?? DEFAULT_TABLE_PAGE_SIZE;
  } catch {
    // A full or disabled localStorage should never break a table.
    return DEFAULT_TABLE_PAGE_SIZE;
  }
}

function storeTablePageSize(storageKey: string, size: TablePageSize) {
  try {
    window.localStorage.setItem(storageKey, String(size));
  } catch {
    // The table keeps its in-memory page size when storage is unavailable.
  }
}

/**
 * Page a table by whole rows and remember its rows-per-page setting.
 *
 * `storageKey` belongs to the table, not just the app: two tables can keep
 * different sizes, and a size stored by an older build is ignored unless it is
 * still one of `TABLE_PAGE_SIZES`.
 */
export function useTablePagination<T>(rows: readonly T[], storageKey: string) {
  const [pageSize, setPageSizeState] = useState<TablePageSize>(() =>
    storedTablePageSize(storageKey),
  );
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(Math.max(1, page), pageCount);

  // Purchases can disappear or a larger page size can shrink the table while it
  // is open; keep the state on the last real page instead of an empty one.
  useEffect(() => {
    if (page !== currentPage) setPage(currentPage);
  }, [page, currentPage]);

  const pageRows = useMemo(
    () => rows.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [rows, currentPage, pageSize],
  );

  function setPageSize(size: TablePageSize) {
    setPageSizeState(size);
    setPage(1);
    storeTablePageSize(storageKey, size);
  }

  return {
    page: currentPage,
    pageCount,
    pageSize,
    pageRows,
    total: rows.length,
    setPage,
    setPageSize,
  };
}

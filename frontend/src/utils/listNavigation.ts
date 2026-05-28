export type ListNavigationState = {
  listSearch: string;
};

export function listLinkState(
  searchParams: URLSearchParams,
): ListNavigationState {
  return { listSearch: searchParams.toString() };
}

export function listReturnTo(state: unknown) {
  const listSearch = (state as ListNavigationState | null)?.listSearch;
  if (listSearch) {
    return { pathname: "/", search: `?${listSearch}` };
  }
  return "/";
}

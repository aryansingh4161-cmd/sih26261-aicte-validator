import { useQuery } from "@tanstack/react-query";
import { getJSON } from "./client";
import { useSettings } from "../app/settings";

/** Read one view (live API or demo snapshot) for the current language and role. */
export function useView<T>(path: string | null, params?: Record<string, string | undefined>) {
  const { lang, role } = useSettings();
  return useQuery<T>({
    queryKey: [path, lang, role, params],
    queryFn: () => getJSON<T>(path as string, { lang, role, params }),
    enabled: !!path,
    staleTime: 30_000,
    retry: 1,
  });
}

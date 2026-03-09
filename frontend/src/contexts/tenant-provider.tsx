import { useCallback, useMemo, useState, type ReactNode } from "react";
import {
  TenantContext,
  extractTenantWithBasePath,
  type TenantContextValue,
} from "./tenant-context";

export interface TenantProviderProps {
  children: ReactNode;
  /** Base domain for subdomain parsing (default: echo9.net) */
  domain?: string;
}

export function TenantProvider({
  children,
  domain = "echo9.net",
}: TenantProviderProps) {
  const extract = useCallback(
    () => extractTenantWithBasePath(domain),
    [domain]
  );

  const [tenantData, setTenantData] = useState<{
    slug: string | null;
    basePath: string;
  }>(() => {
    const r = extract();
    return r ? { slug: r.slug, basePath: r.basePath } : { slug: null, basePath: "" };
  });

  const refresh = useCallback(() => {
    const r = extract();
    setTenantData(
      r ? { slug: r.slug, basePath: r.basePath } : { slug: null, basePath: "" }
    );
  }, [extract]);

  const value = useMemo<TenantContextValue>(
    () => ({
      tenantSlug: tenantData.slug,
      hasTenant: tenantData.slug !== null,
      tenantBasePath: tenantData.basePath,
      refresh,
    }),
    [tenantData, refresh]
  );

  return (
    <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
  );
}

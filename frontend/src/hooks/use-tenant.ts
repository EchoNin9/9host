import { useContext } from "react";
import { TenantContext } from "@/contexts/tenant-context";

export function useTenant() {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error("useTenant must be used within TenantProvider");
  }
  return ctx;
}

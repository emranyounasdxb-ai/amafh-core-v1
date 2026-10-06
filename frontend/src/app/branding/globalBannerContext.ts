import { createContext, useContext } from "react";

export type BannerContextValue = {
  fileId: string | null;
  imageUrl: string;
  loading: boolean;
  error: string;
  reload: () => void;
  retry: () => void;
  confirmReset: () => void;
};

export const BannerContext = createContext<BannerContextValue | null>(null);

export function useGlobalBanner() {
  const context = useContext(BannerContext);
  if (!context) throw new Error("GlobalBannerProvider required");
  return context;
}

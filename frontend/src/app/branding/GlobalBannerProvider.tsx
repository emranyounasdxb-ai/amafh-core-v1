import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { AuthenticatedSession } from "../api/contracts";
import { ApiFailure } from "../api/http";
import { useResource } from "../api/useResource";
import { useSession } from "../session/useSession";
import { BannerContext } from "./globalBannerContext";

type BannerReference = { fileId: string | null };
type BannerImage = {
  session: AuthenticatedSession;
  fileId: string;
  generation: number;
  url: string;
};
type BannerImageError = {
  session: AuthenticatedSession;
  fileId: string;
  generation: number;
  message: string;
  denied: boolean;
};
type BannerScope = {
  session: AuthenticatedSession | null;
  fileId: string | null;
  denied: boolean;
  resetPending: boolean;
  generation: number;
};

const DEFAULT_BANNER = "/profile-banner-cover.png";

export function GlobalBannerProvider({ children }: { children: ReactNode }) {
  const { api, session } = useSession();
  const banner = useResource<BannerReference>(
    session ? "/branding/profile-banner" : null,
  );
  const [image, setImage] = useState<BannerImage | null>(null);
  const [imageError, setImageError] = useState<BannerImageError | null>(null);
  const [imageRetry, setImageRetry] = useState(0);
  const [resetFile, setResetFile] = useState<{
    session: AuthenticatedSession;
    fileId: string;
  } | null>(null);
  const allocatedUrls = useRef<Set<string>>(new Set());
  const fileId = banner.data?.fileId ?? null;
  const resetPending =
    resetFile?.session === session && resetFile.fileId === fileId;
  const [scope, setScope] = useState<BannerScope>(() => ({
    session,
    fileId,
    denied: banner.denied,
    resetPending,
    generation: 0,
  }));
  if (
    scope.session !== session ||
    scope.fileId !== fileId ||
    scope.denied !== banner.denied ||
    scope.resetPending !== resetPending
  ) {
    const invalidated =
      scope.session !== session ||
      (scope.fileId !== null && fileId === null) ||
      (!scope.denied && banner.denied) ||
      (!scope.resetPending && resetPending);
    setScope({
      session,
      fileId,
      denied: banner.denied,
      resetPending,
      generation: scope.generation + Number(invalidated),
    });
  }
  const currentError =
    imageError?.session === session &&
    imageError.fileId === fileId &&
    imageError.generation === scope.generation
      ? imageError
      : null;
  const imageDenied = currentError?.denied === true;
  const visibleImage =
    session &&
    fileId &&
    !banner.denied &&
    !resetPending &&
    !imageDenied &&
    image?.session === session &&
    image.generation === scope.generation
      ? image
      : null;

  useLayoutEffect(() => {
    for (const url of allocatedUrls.current) {
      if (url === visibleImage?.url) continue;
      URL.revokeObjectURL(url);
      allocatedUrls.current.delete(url);
    }
  });
  useLayoutEffect(
    () => () => {
      for (const url of allocatedUrls.current) URL.revokeObjectURL(url);
      allocatedUrls.current.clear();
    },
    [],
  );

  useEffect(() => {
    if (!session || !fileId || banner.denied || resetPending || imageDenied)
      return;
    const controller = new AbortController();
    let pendingUrl: string | null = null;
    api
      .response(`/branding/profile-banner/files/${fileId}`, {
        signal: controller.signal,
      })
      .then((response) => response.blob())
      .then(async (blob) => {
        if (controller.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        pendingUrl = url;
        const decoded = new Image();
        decoded.src = url;
        await decoded.decode();
        if (controller.signal.aborted) return;
        pendingUrl = null;
        allocatedUrls.current.add(url);
        setImage({ session, fileId, generation: scope.generation, url });
        setImageError(null);
      })
      .catch((error: unknown) => {
        if (pendingUrl) {
          URL.revokeObjectURL(pendingUrl);
          pendingUrl = null;
        }
        if (!controller.signal.aborted) {
          const denied =
            error instanceof ApiFailure &&
            [401, 403, 404].includes(error.status);
          if (denied)
            setScope((previous) =>
              previous.session === session &&
              previous.generation === scope.generation
                ? { ...previous, generation: previous.generation + 1 }
                : previous,
            );
          setImageError({
            session,
            fileId,
            generation: scope.generation + Number(denied),
            message:
              error instanceof Error
                ? error.message
                : "Banner image unavailable",
            denied,
          });
        }
      });
    return () => {
      controller.abort();
      if (pendingUrl) {
        URL.revokeObjectURL(pendingUrl);
        pendingUrl = null;
      }
    };
  }, [
    api,
    session,
    fileId,
    banner.denied,
    resetPending,
    imageDenied,
    imageRetry,
    scope.generation,
  ]);

  const reload = () => banner.reload();
  const retry = () => {
    if (banner.error) banner.reload();
    else {
      setImageError(null);
      setImageRetry((value) => value + 1);
    }
  };
  const confirmReset = () => {
    if (session && fileId) setResetFile({ session, fileId });
    setImageError(null);
    banner.reload();
  };
  return (
    <BannerContext.Provider
      value={{
        fileId: resetPending ? null : fileId,
        imageUrl: visibleImage?.url || DEFAULT_BANNER,
        loading: banner.loading,
        error: banner.error || currentError?.message || "",
        reload,
        retry,
        confirmReset,
      }}
    >
      {children}
    </BannerContext.Provider>
  );
}

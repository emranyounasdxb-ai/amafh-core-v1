import { useState } from "react";
import {
  Button,
  FileUpload,
  InlineNotice,
  SectionCard,
  Stack,
} from "../../../design-system";
import { useGlobalBanner } from "../../../app/branding/globalBannerContext";
import { ApiFailure } from "../../../app/api/http";
import { useSession } from "../../../app/session/useSession";
import styles from "./SettingsPage.module.css";

export function BrandingSettings() {
  const { api, session } = useSession();
  const banner = useGlobalBanner();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  if (session?.designation !== "Owner") return null;
  const failureText = (failure: unknown, fallback: string) =>
    failure instanceof ApiFailure ? failure.message : fallback;
  const upload = async (next: FileList | null) => {
    setFiles(next);
    const file = next?.[0];
    if (!file) return;
    setBusy(true);
    setMessage("");
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      await api.request("/branding/profile-banner", { method: "PUT", body });
      banner.reload();
      setMessage("Global profile banner saved.");
    } catch (failure) {
      setError(failureText(failure, "The banner could not be uploaded."));
    } finally {
      setBusy(false);
    }
  };
  const reset = async () => {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await api.request("/branding/profile-banner/reset", { method: "POST" });
      banner.confirmReset();
      setFiles(null);
      setMessage("Built-in default banner restored.");
    } catch (failure) {
      setError(failureText(failure, "The banner could not be reset."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <SectionCard
      title="Global profile banner"
      description="Shown on every employee profile."
    >
      <Stack>
        <div
          className={styles.banner}
          role="img"
          aria-label="Current global profile banner"
          style={{ backgroundImage: `url("${banner.imageUrl}")` }}
        />
        <FileUpload
          id="settings-branding-banner"
          label={banner.fileId ? "Replace banner" : "Upload banner"}
          hint="JPEG, PNG, or WebP"
          accept="image/jpeg,image/png,image/webp"
          files={files}
          busy={busy}
          error={error || undefined}
          onChange={(next) => void upload(next)}
        />
        <div>
          <Button
            variant="secondary"
            disabled={busy || !banner.fileId}
            onClick={() => void reset()}
          >
            Reset to built-in default
          </Button>
        </div>
        {message ? <InlineNotice tone="success">{message}</InlineNotice> : null}
        {banner.error ? (
          <InlineNotice tone="error" title="Banner unavailable">
            {banner.error}{" "}
            <Button size="compact" variant="secondary" disabled={busy} onClick={banner.retry}>
              Retry banner
            </Button>
          </InlineNotice>
        ) : null}
      </Stack>
    </SectionCard>
  );
}

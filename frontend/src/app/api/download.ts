import type { ApiClient } from "./http";

export async function download(
  api: ApiClient,
  path: string,
  init?: RequestInit,
) {
  const response = await api.response(path, init);
  const match = /filename="?([^";]+)"?/i.exec(
    response.headers.get("Content-Disposition") || "",
  );
  const name =
    match?.[1]
      ?.split("")
      .map((character) =>
        character.charCodeAt(0) < 32 || "/\\".includes(character)
          ? "_"
          : character,
      )
      .join("") || "download";
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

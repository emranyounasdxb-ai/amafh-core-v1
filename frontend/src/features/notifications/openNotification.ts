import type { AccessSession, PageId } from "../../access";
import { canOpenPage } from "../../access";
import { ApiFailure, type ApiClient } from "../../app/api/http";
import {
  apiPathFromDestination,
  destinationPageForResource,
  routeFromApiPath,
} from "../../app/navigation/destinationRoute";

export type NotificationOpenResult =
  | { status: "opened"; page: PageId; recordId?: string }
  | { status: "unavailable" }
  | { status: "permission" };

export async function openNotificationDestination(
  api: ApiClient,
  notificationId: string,
  session: AccessSession,
): Promise<NotificationOpenResult> {
  try {
    const result = await api.request<{ path: string }>(
      `/notifications/${notificationId}/destination`,
    );
    if (!result.path.startsWith("/api/v1/")) return { status: "unavailable" };
    const route = routeFromApiPath(result.path, session);
    if (route) return { status: "opened", ...route };
    const resource = apiPathFromDestination(result.path)
      .split("/")
      .filter(Boolean)[0];
    const page = destinationPageForResource(resource);
    if (page && !canOpenPage(session, page)) return { status: "permission" };
    return { status: "unavailable" };
  } catch (failure) {
    if (failure instanceof ApiFailure && failure.status === 403)
      return { status: "permission" };
    return { status: "unavailable" };
  }
}

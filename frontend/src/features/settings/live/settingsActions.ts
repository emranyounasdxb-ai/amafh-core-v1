import type { ReactNode } from "react";
import type { Command } from "../../../app/api/commands";
import type { DataRecord } from "../../../app/api/models";

export type SettingsFact = { label: string; value: ReactNode; numeric?: boolean };

export type SettingsAction =
  | {
      id: string;
      label: string;
      success: string;
      command: Command;
      record?: DataRecord;
    }
  | {
      id: string;
      label: string;
      success: string;
      confirm: {
        title: string;
        path: string;
        message: string;
        danger?: boolean;
      };
    };

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Activate or deactivate; configuration records are never deleted. */
export function stateAction(
  noun: string,
  path: string,
  active: boolean,
  message?: string,
): SettingsAction {
  return active
    ? {
        id: "deactivate",
        label: `Deactivate ${noun}`,
        success: `${capitalize(noun)} deactivated.`,
        confirm: {
          title: `Deactivate ${noun}`,
          path: `${path}/deactivate`,
          danger: true,
          message:
            message ??
            `This ${noun} stops being offered for new selections. Its history and relationships are retained.`,
        },
      }
    : {
        id: "activate",
        label: `Activate ${noun}`,
        success: `${capitalize(noun)} activated.`,
        confirm: {
          title: `Activate ${noun}`,
          path: `${path}/activate`,
          message: `This ${noun} becomes available for new selections again.`,
        },
      };
}

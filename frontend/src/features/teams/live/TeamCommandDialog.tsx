import { useState } from "react";
import {
  DestructiveConfirmationDialog,
  EmptyValue,
  InfoField,
  InfoGrid,
  InlineNotice,
  Stack,
} from "../../../design-system";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { ApiFailure } from "../../../app/api/http";
import { useSession } from "../../../app/session/useSession";
import {
  addMemberCommand,
  reassignLeaderCommand,
  renameTeamCommand,
  type TeamScope,
} from "./teamCommands";

export type TeamCommand =
  | { kind: "rename" | "leader" | "member" | "deactivate" }
  | { kind: "remove"; memberId: string; memberName: string };

export function TeamCommandDialog({
  command,
  team,
  name,
  branch,
  department,
  leader,
  onClose,
  onSaved,
}: {
  command: TeamCommand;
  team: TeamScope;
  name: string;
  branch: string;
  department: string;
  leader: string;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (command.kind === "rename")
    return (
      <CommandFormDialog
        command={renameTeamCommand(team)}
        record={{ name }}
        onClose={onClose}
        onSaved={() => onSaved("Team renamed.")}
      />
    );
  if (command.kind === "leader")
    return (
      <CommandFormDialog
        command={reassignLeaderCommand(team)}
        onClose={onClose}
        onSaved={() => onSaved("Team Leader changed.")}
      />
    );
  if (command.kind === "member")
    return (
      <CommandFormDialog
        command={addMemberCommand(team)}
        onClose={onClose}
        onSaved={() => onSaved("Member added.")}
      />
    );

  const removing = command.kind === "remove";
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      await api.request(
        removing
          ? `/teams/${team.id}/members/${command.memberId}/end`
          : `/teams/${team.id}/deactivate`,
        { method: "POST" },
      );
      onSaved(removing ? "Membership ended." : "Team deactivated.");
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "The request could not be completed. Retry safely when the connection returns.",
      );
    } finally {
      setBusy(false);
    }
  };
  const fact = (label: string, value: string) => (
    <InfoField key={label} label={label} value={value || <EmptyValue />} />
  );

  return (
    <DestructiveConfirmationDialog
      open
      title={removing ? "Remove member" : "Deactivate Team"}
      confirmLabel={removing ? "Remove member" : "Deactivate Team"}
      busy={busy}
      onClose={onClose}
      onConfirm={() => void run()}
    >
      <Stack>
        <InfoGrid>
          {removing ? fact("Member", command.memberName) : null}
          {fact("Team", name)}
          {fact("Branch", branch)}
          {fact("Department", department)}
          {removing ? null : fact("Team Leader", leader)}
        </InfoGrid>
        <p>
          {removing
            ? "The member’s current Team membership ends today. Membership history is retained."
            : "Deactivating the Team ends its active leadership and memberships. The Team record and its history are retained."}
        </p>
        {error ? (
          <InlineNotice tone="error" title="Unable to continue">
            {error}
          </InlineNotice>
        ) : null}
      </Stack>
    </DestructiveConfirmationDialog>
  );
}

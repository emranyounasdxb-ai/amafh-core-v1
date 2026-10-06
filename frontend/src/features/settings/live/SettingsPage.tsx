import type { ReactNode } from "react";
import {
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  SearchResultsList,
  SectionCard,
} from "../../../design-system";
import { useSession } from "../../../app/session/useSession";
import { FinancialRulesPanel } from "../../finance/live/RulesView";
import { AuditLog } from "../AuditLog";
import { SettingsSectionContent } from "./settingsSections";
import { authorizedSettings, type SettingsSection } from "./settingsRegistry";
import styles from "./SettingsPage.module.css";

export function SettingsPage({
  sectionId,
  open,
}: {
  sectionId?: string;
  open: (sectionId?: string) => void;
}) {
  const { session } = useSession();
  const sections = authorizedSettings(session);
  const only = sections.length === 1 ? sections[0] : undefined;
  const requested = sectionId
    ? sections.find((section) => section.id === sectionId)
    : only;

  if (sectionId && !requested)
    return (
      <PageContainer>
        <div className={styles.page}>
          <PageHeader
            title="Settings"
            onBack={sections.length ? () => open() : undefined}
            backLabel="Settings"
          />
          <PermissionDeniedState
            title="Setting unavailable"
            description="This setting is unavailable or outside your authorized access."
          />
        </div>
      </PageContainer>
    );

  if (requested)
    return (
      <PageContainer>
        <div className={styles.page}>
          <PageHeader
            title={requested.title}
            subtitle={requested.description}
            onBack={only ? undefined : () => open()}
            backLabel="Settings"
          />
          <SectionBody section={requested} />
        </div>
      </PageContainer>
    );

  const groups = [...new Set(sections.map((section) => section.group))];
  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Settings"
          subtitle="Approved configuration and immutable history"
        />
        <div className={styles.groups}>
          {groups.map((group) => (
            <SectionCard key={group} title={group} compact>
              <SearchResultsList
                items={sections
                  .filter((section) => section.group === group)
                  .map((section) => ({
                    id: section.id,
                    title: section.title,
                    meta: section.description,
                    onSelect: () => open(section.id),
                  }))}
              />
            </SectionCard>
          ))}
        </div>
      </div>
    </PageContainer>
  );
}

function SectionBody({ section }: { section: SettingsSection }): ReactNode {
  if (section.id === "financial-rules") return <FinancialRulesPanel />;
  if (section.id === "audit") return <AuditLog />;
  return <SettingsSectionContent id={section.id} />;
}

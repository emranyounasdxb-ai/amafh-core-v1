import { useState } from "react";
import {
  InlineNotice,
  PageContainer,
  PageHeader,
  Tabs,
} from "../../../design-system";
import { canManageFinance, canViewFinanceLedgers } from "../../../access";
import { useSession } from "../../../app/session/useSession";
import { ClawbacksView } from "./ClawbacksView";
import { CompletedCasesView } from "./CompletedCasesView";
import { financeViews, VIEW_LABEL, type FinanceView } from "./financeRecords";
import { PaymentsView } from "./PaymentsView";
import { RulesView } from "./RulesView";
import { WalletsView } from "./WalletsView";
import styles from "./FinancePage.module.css";

export function FinancePage() {
  const { session } = useSession();
  const manage = session ? canManageFinance(session) : false;
  const ledgers = session ? canViewFinanceLedgers(session) : false;
  const views = financeViews(ledgers);
  const [view, setView] = useState<FinanceView>("completed-cases");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState("");
  const active = views.includes(view) ? view : "completed-cases";
  const saved = (message: string) => {
    setNotice(message);
    setRefresh((value) => value + 1);
  };
  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Finance"
          subtitle="Completed case credits, points, clawbacks, payments, and rules"
        />
        <Tabs
          label="Finance views"
          value={active}
          onChange={(next) => {
            setView(next as FinanceView);
            setNotice("");
          }}
          items={views.map((item) => ({ id: item, label: VIEW_LABEL[item] }))}
        />
        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}
        {active === "completed-cases" ? (
          <CompletedCasesView refresh={refresh} showRule={ledgers} />
        ) : active === "wallets" ? (
          <WalletsView refresh={refresh} />
        ) : active === "clawbacks" ? (
          <ClawbacksView refresh={refresh} manage={manage} onSaved={saved} />
        ) : active === "payments" ? (
          <PaymentsView refresh={refresh} manage={manage} onSaved={saved} />
        ) : (
          <RulesView refresh={refresh} onSaved={saved} />
        )}
      </div>
    </PageContainer>
  );
}

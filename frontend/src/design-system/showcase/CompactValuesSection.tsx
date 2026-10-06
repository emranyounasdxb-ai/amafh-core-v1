import {
  CompactNumber,
  MetricValue,
  MonetaryAmount,
  SectionCard,
} from "../index";

export function CompactValuesSection() {
  return (
    <section id="compact-values" className="ds-stack-20">
      <SectionCard
        title="Monetary amounts"
        description="Read-only AED values use one formatter. The official Dirham symbol is preferred when the bundled font can render it; otherwise AED. Hover or focus reveals the full AED value. Whole amounts never show .00."
      >
        <div className="ds-compact-examples">
          <article>
            <span>Zero</span>
            <MonetaryAmount value={0} />
          </article>
          <article>
            <span>Below 1,000</span>
            <MonetaryAmount value={950} />
          </article>
          <article>
            <span>1K</span>
            <MonetaryAmount value={1_000} />
          </article>
          <article>
            <span>1.5K</span>
            <MonetaryAmount value={1_500} />
          </article>
          <article>
            <span>25K</span>
            <MonetaryAmount value={25_000} />
          </article>
          <article>
            <span>250K</span>
            <MonetaryAmount value={250_000} />
          </article>
          <article>
            <span>1M</span>
            <MonetaryAmount value={1_000_000} />
          </article>
          <article>
            <span>1.25M</span>
            <MonetaryAmount value={1_250_000} />
          </article>
          <article>
            <span>300M</span>
            <MonetaryAmount value={300_000_000} />
          </article>
          <article>
            <span>1B</span>
            <MonetaryAmount value={1_000_000_000} />
          </article>
          <article>
            <span>Fils</span>
            <MonetaryAmount value={25_000.5} />
          </article>
          <article>
            <span>Negative</span>
            <MonetaryAmount value={-12_500} />
          </article>
          <article>
            <span>Unavailable</span>
            <MonetaryAmount value={null} />
          </article>
        </div>
      </SectionCard>
      <SectionCard
        title="Compact values"
        description="Non-monetary counts keep CompactNumber. Do not apply K/M/B money formatting to points, percentages, or identifiers."
      >
        <div className="ds-compact-examples">
          <article>
            <span>Ordinary count</span>
            <CompactNumber value={18} compactDecimals={0} />
          </article>
          <article>
            <span>Thousands</span>
            <CompactNumber value={1250} />
          </article>
          <article>
            <span>Millions</span>
            <CompactNumber value={12_450_000.75} />
          </article>
          <article>
            <span>Billions</span>
            <CompactNumber value={1_250_000_000} />
          </article>
          <article>
            <span>Percentage</span>
            <MetricValue value={81.25} kind="percent" fullDecimals={2} />
          </article>
          <article>
            <span>One decimal</span>
            <CompactNumber value={300_500_000} compactDecimals={1} />
          </article>
          <article>
            <span>Two decimals</span>
            <CompactNumber value={300_550_000} compactDecimals={2} />
          </article>
        </div>
      </SectionCard>
    </section>
  );
}

const COMPANY_COVERAGE_COPY = new Map([
  ["Explicit simulated company source manifest; completeness applies only to exact received source rows.", "Coverage is complete only for the source rows received."],
  ["The regenerated source explicitly attests its full as-of day; later days are unknown and no holdout truth is used.", "The source is complete through its stated as-of day. Later days remain unknown; future outcomes are not used."],
  ["Historical replay requires chronological native receipts; issued ForecastService snapshots preserve prior vintages.", "Historical comparisons require records received in time order. Published forecasts remain fixed."],
]);

/** App-owned display labels only. Do not use this for source quotations or user-authored text. */
export function displayCopy(value: string | null | undefined, fallback = ""): string {
  if (!value) return fallback;
  const coverageCopy = COMPANY_COVERAGE_COPY.get(value);
  if (coverageCopy) return coverageCopy;
  const text = value
    .replace(/^Synthetic demo:\s*/i, "")
    .replace(/^Demo:\s*/i, "")
    .replace(/\bDeterministic synthetic Northstar fixture\b/gi, "Planning assumptions")
    .replace(/\bSynthetic Northstar Fixture\b/gi, "Northstar")
    .replace(/\bSynthetic Northstar observed usage\b/g, "Northstar observed usage")
    .replace(/\bSynthetic demo data\b/gi, "Data")
    .replace(/\bSynthetic demo ledger\b/gi, "Ledger")
    .replace(/\bDemo data\b/g, "Data")
    .replace(/\bScripted assistant\b/g, "Assistant")
    .replace(/\bSupplied synthetic planning totals\b/g, "Supplied planning totals")
    .replace(/\bSynthetic quarter continuation\b/g, "Quarter continuation")
    .replace(/\bSynthetic illustration\b/g, "Illustration")
    .replace(/\bsynthetic UI fixture\b/gi, "Planning illustration")
    .replace(/\bSynthetic source context has no measured financial effect\b/g, "Source context has no measured financial effect")
    .replace(/^Synthetic fixture assessment against matching team allocation and issued full-period forecast\./, "Assessment against matching team allocation and issued full-period forecast.")
    .replace(/^Duplicate team allocation in this fixture\.$/, "Duplicate team allocation in this planning data.")
    .replace(/^A request evidence reference is not available in this fixture\.$/, "A request evidence reference is not available in this planning data.")
    .replace(/^This forecast-demo person has no repository ledger identity: unavailable attribution, not zero spend\.$/, "This person has no repository ledger identity: unavailable attribution, not zero spend.")
    .replace(/^Synthetic usage(?=[.;:]|$)/, "Usage")
    .replace(/^Synthetic inputs are incomplete\b/, "Inputs are incomplete")
    .replace(/^Scripted source unavailable\b/, "Source unavailable")
    .replace(/\bToken totals are generated from fixture pricing\b/g, "Token totals are generated from supplied pricing")
    .replace(/ \((?:demo|synthetic|fixture|simulated)\)$/, "");
  return text || fallback;
}

/** Preserve source quotations, document bodies and user-authored wording verbatim. */
export function displaySourceText(value: string | null | undefined, fallback = ""): string {
  return value || fallback;
}

// Only repository-generated identity formats are presentation noise. Domain references
// such as synthetic-biology or product-demo-videos remain meaningful source identities.
const GENERATED_REFERENCE = /^(?:(?:synthetic|fixture|demo)[-_:](?:ui[-_:])?(?:run|driver|source|document|revision|target|refresh|weekly(?:-v\d+)?|outcome-v\d+|observed-outcome|ledger(?:-v\d+)?|spend)(?:$|[-_:])|synthetic(?::|_\d|[-_]\d)|snap_fixture_|(?:budget-request:)?mock-request:|forecast-demo-\d|finance-demo$)/i;

/** Keep original audit references unless they match a known generated identity format. */
export function displayReference(value: string | null | undefined, fallback = "Saved record"): string {
  if (!value || GENERATED_REFERENCE.test(value) || /^Synthetic Northstar Fixture$/i.test(value)) return fallback;
  return value;
}

const INTERNAL_FIELDS = new Set(["is_synthetic", "isSynthetic", "synthetic", "is_demo", "isDemo", "demo", "dataset_id", "datasetId", "source_record_key", "sourceRecordKey"]);
/** A new display value; never mutate the authoritative object or use this for calculations. */
export function safeDisplayMetadata(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(safeDisplayMetadata);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).filter(([key]) => !INTERNAL_FIELDS.has(key)).map(([key, item]) => [key === "fixture_note" ? "note" : key, safeDisplayMetadata(item)]));
  }
  if (typeof value === "string") return GENERATED_REFERENCE.test(value) ? "Saved record" : displayCopy(value);
  return value;
}

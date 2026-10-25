import type { ForecastBundle, ForecastRefresh, ForecastScenarioReceipt, ForecastScenarioResponse } from "../contracts/forecast-view";

type ScenarioClient = {
  getForecastRefresh(id: string): Promise<ForecastRefresh>;
  getForecastScenario(id: string): Promise<ForecastScenarioResponse>;
};

/** Receipts are job state, never a substitute for a completed isolated scenario bundle. */
export async function completeScenario(
  response: ForecastScenarioResponse,
  parentRun: string,
  client: ScenarioClient,
  onProgress: (receipt: ForecastScenarioReceipt) => void,
  options: { maxPolls?: number; delay?: () => Promise<void> } = {},
): Promise<ForecastBundle> {
  const delay = options.delay ?? (() => new Promise(resolve => setTimeout(resolve,500)));
  const maxPolls = options.maxPolls ?? 120;
  let current = response;
  for (let attempt = 0; attempt <= maxPolls; attempt++) {
    if (current.parent_run_id && current.parent_run_id !== parentRun) throw new Error("Scenario response belongs to a different issued run.");
    const receipt = current as ForecastScenarioReceipt;
    if (!receipt.job_id || !receipt.status || receipt.status === "succeeded" && current.views?.length) return current as ForecastBundle;
    onProgress(receipt);
    if (receipt.status === "failed") throw new Error(receipt.last_error ?? "Scenario job failed. Retry preview to create another isolated job.");
    if (attempt === maxPolls) throw new Error("Scenario is still queued or running. Check scenario status to resume this job.");
    await delay();
    const job = await client.getForecastRefresh(receipt.job_id);
    if (job.run_id && job.run_id !== receipt.scenario_id) throw new Error("Scenario job returned a different scenario identity.");
    if (job.status === "succeeded") {
      current = await client.getForecastScenario(receipt.scenario_id);
    } else {
      current = { ...receipt, status:job.status, last_error: typeof job.last_error === "string" ? job.last_error : receipt.last_error };
    }
  }
  throw new Error("Scenario did not complete.");
}

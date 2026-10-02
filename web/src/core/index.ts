/**
 * Shared Stage A → Stage B runners used by the WASM PWA and the Node CLI.
 * UI-independent core (not the CLI itself — see repo-root `cli/`).
 */
export {
  runRuleD5,
  runRuleD5FromRepairText,
  runRuleD5Synthetic,
  type RuleD5RunInput,
  type RuleD5RunResult,
} from "./ruleD5";

export {
  runColregs,
  type ColregsRunInput,
  type ColregsRunResult,
} from "./colregs";

export {
  runPsc,
  runPscFromPaste,
  runPscFixture,
  type PscRunInput,
  type PscRunResult,
} from "./psc";

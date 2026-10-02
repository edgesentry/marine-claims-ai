import { describe, expect, it } from "vitest";
import golden from "./fixtures/rule_d5_golden.json";
import {
  apportionRuleD,
  type DockingContext,
  type RepairLineItem,
} from "../src/engines/ruleD5";

describe("Rule D5 golden (0 JPY recon)", () => {
  for (const case_ of golden) {
    it(case_.id, () => {
      const result = apportionRuleD(
        case_.items as RepairLineItem[],
        case_.docking_context as DockingContext,
      );
      expect(result.has_statutory_owner_repair).toBe(case_.expect.has_statutory_owner_repair);
      expect(result.apportionment_rule).toBe(case_.expect.apportionment_rule);
      expect(result.common_dues_total).toBe(case_.expect.common_dues_total);
      expect(result.insurer_common_share).toBe(case_.expect.insurer_common_share);
      expect(result.owner_common_share).toBe(case_.expect.owner_common_share);
      expect(result.insurer_common_share + result.owner_common_share).toBe(
        result.common_dues_total,
      );
      expect(result.insurer_total).toBe(case_.expect.insurer_total);
      expect(result.owner_total).toBe(case_.expect.owner_total);
      for (const ln of result.lines) {
        expect(ln.insurer_share + ln.owner_share).toBe(ln.cost);
      }
      expect(result.insurer_total + result.owner_total).toBe(result.claimed_total);
    });
  }
});

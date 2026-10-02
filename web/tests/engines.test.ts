import { describe, expect, it } from "vitest";
import {
  classifyEncounter,
  isHeadOn,
  isOvertaking,
  relativeBearingDeg,
} from "../src/engines/colregs";
import {
  buildCompartmentGraph,
  hasPath,
  shortestPath,
  validateCausality,
  validateClaimsCausality,
} from "../src/engines/bfs";
import { cosineSimilarity, hashEmbed, knnByCosine } from "../src/engines/fault";

describe("COLREGS", () => {
  it("relative bearing", () => {
    expect(relativeBearingDeg(90, 0)).toBe(90);
    expect(relativeBearingDeg(0, 350)).toBe(10);
  });

  it("overtaking sector", () => {
    expect(isOvertaking(180)).toBe(true);
    expect(isOvertaking(90)).toBe(false);
  });

  it("head-on", () => {
    expect(isHeadOn(180, 0)).toBe(true);
    expect(isHeadOn(90, 0)).toBe(false);
  });

  it("crossing civil_7-like geometry", () => {
    const v = classifyEncounter({
      heading_a_deg: 30,
      heading_b_deg: 300,
      true_bearing_a_to_b_deg: 70,
      speed_a_kn: 12,
      speed_b_kn: 10,
      range_nm: 0.8,
    });
    expect(v.situation).toBe("crossing");
    expect(v.role_a).toBe("give_way");
    expect(v.role_b).toBe("stand_on");
  });
});

describe("BFS compartments", () => {
  it("machinery is isolated from bow", () => {
    const g = buildCompartmentGraph();
    expect(hasPath(g, "hull_forward", "machinery")).toBe(false);
    expect(validateCausality("船首", "機関室").valid).toBe(false);
    expect(validateCausality("船首", "機関室").reason).toBe("watertight_barrier_violation");
  });

  it("adjacent hull path", () => {
    const path = shortestPath(buildCompartmentGraph(), "hull_forward", "hull_aft");
    expect(path).toEqual(["hull_forward", "hull_mid", "hull_aft"]);
    const claims = validateClaimsCausality("船首", "船尾", 1);
    expect(claims.valid).toBe(false);
    expect(claims.reason).toBe("beyond_casualty_propagation_limit");
  });
});

describe("fault cosine embeddings", () => {
  it("identical text → cosine ~ 1", () => {
    const a = hashEmbed("霧中 見張り不十分 横切");
    const b = hashEmbed("霧中 見張り不十分 横切");
    expect(cosineSimilarity(a, b)).toBeCloseTo(1, 5);
  });

  it("knn returns neighbors", () => {
    const { matches, bestScore } = knnByCosine(
      "crossing collision lookout failure",
      [
        {
          case_id: "1",
          title: "crossing lookout",
          input_facts: "crossing collision lookout failure fog",
          fault_ratio: "80:20",
        },
        {
          case_id: "2",
          title: "unrelated berth",
          input_facts: "mooring line parted at berth",
          fault_ratio: "50:50",
        },
      ],
      2,
    );
    expect(matches[0]!.case_id).toBe("1");
    expect(bestScore).toBeGreaterThan(0);
  });
});

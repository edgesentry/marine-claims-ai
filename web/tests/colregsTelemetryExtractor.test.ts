/**
 * COLREGS Stage A telemetry extractor (#91) — unit coverage.
 */
import { describe, expect, it } from "vitest";
import { classifyEncounter } from "../src/engines/colregs";
import {
  extractColregsTelemetry,
  isCompleteTelemetry,
  telemetryToGeometry,
} from "../src/ingest/colregsTelemetryExtractor";

describe("extractColregsTelemetry", () => {
  it("extracts Kii crossing headings and starboard relative → true bearing", () => {
    const text =
      "本船Ａは針路０３０度、速力約１２ノットで進行中、右舷前約４０度に相手船Ｂを視認した。相手船Ｂは針路３００度、速力約１０ノットで航行していた。";
    const ext = extractColregsTelemetry(text);
    expect(ext.heading_a?.value).toBe(30);
    expect(ext.heading_b?.value).toBe(300);
    expect(ext.relative_bearing_a_to_b?.value).toBe(40);
    expect(ext.true_bearing_a_to_b?.value).toBe(70);
    expect(ext.speed_a_kn?.value).toBe(12);
    expect(ext.speed_b_kn?.value).toBe(10);
    expect(isCompleteTelemetry(ext)).toBe(true);
    const geom = telemetryToGeometry(ext)!;
    const verdict = classifyEncounter(geom);
    expect(verdict.situation).toBe("crossing");
    expect(verdict.role_a).toBe("give_way");
    expect(verdict.role_b).toBe("stand_on");
  });

  it("maps port relative bearing to true bearing", () => {
    const text =
      "本船Ａは針路０００度、速力約１１ノットで進行中、左舷前約６０度に相手船Ｂを視認した。相手船Ｂは針路０９０度、速力約９ノットであった。";
    const ext = extractColregsTelemetry(text);
    expect(ext.heading_a?.value).toBe(0);
    expect(ext.heading_b?.value).toBe(90);
    expect(ext.relative_bearing_a_to_b?.value).toBe(300); // -60 → 300
    expect(ext.true_bearing_a_to_b?.value).toBe(300);
    const verdict = classifyEncounter(telemetryToGeometry(ext)!);
    expect(verdict.situation).toBe("crossing");
    expect(verdict.role_a).toBe("stand_on");
  });

  it("parses compass headings", () => {
    const text =
      "本船Ａは針路北東、速力約１２ﾉｯﾄで進行中、右舷前約５０度に相手船Ｂを視認した。相手船Ｂは針路北西、速力約１０ノットで航行していた。";
    const ext = extractColregsTelemetry(text);
    expect(ext.heading_a?.value).toBe(45);
    expect(ext.heading_b?.value).toBe(315);
    expect(ext.true_bearing_a_to_b?.value).toBe(95);
    expect(isCompleteTelemetry(ext)).toBe(true);
  });

  it("parses 北東の微北 compass micro-adjustment", () => {
    const text =
      "本船Ａは針路北東の微北、速力約１１ノットで進行中、右舷前約３５度に相手船Ｂを視認した。相手船Ｂは針路３００度、速力約９ノットであった。";
    const ext = extractColregsTelemetry(text);
    expect(ext.heading_a?.value).toBe(22.5);
    expect(ext.heading_b?.value).toBe(300);
    expect(ext.true_bearing_a_to_b?.value).toBe(57.5);
  });

  it("treats 船首方向 as relative 0°", () => {
    const text =
      "本船Ａは針路０００度、速力約８ノットで進行中、船首方向に相手船Ｂを視認した。相手船Ｂは針路１８０度、速力約９ノットで接近していた。";
    const ext = extractColregsTelemetry(text);
    expect(ext.relative_bearing_a_to_b?.value).toBe(0);
    expect(ext.true_bearing_a_to_b?.value).toBe(0);
    expect(classifyEncounter(telemetryToGeometry(ext)!).situation).toBe("head_on");
  });

  it("returns incomplete when narrative has no numeric geometry", () => {
    const ext = extractColregsTelemetry("両船は横切の関係にあった。");
    expect(isCompleteTelemetry(ext)).toBe(false);
    expect(telemetryToGeometry(ext)).toBeNull();
  });
});

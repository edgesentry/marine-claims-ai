/**
 * Rule D5 Stage A payload (schema_id: rule_d5.v1).
 * Aligns with RepairLineItem + DockingContext consumed by apportionRuleD.
 */
import { z } from "zod";

export const DockingContextSchema = z.enum([
  "casualty_immediate",
  "deferred_to_routine",
]);

export const WorkPartySchema = z.enum(["casualty", "owner", "common"]);

export const OwnerNecessitySchema = z.enum([
  "statutory_seaworthiness",
  "deferred",
  "unspecified",
]);

export const RepairLineSchema = z.object({
  id: z.string().min(1),
  cost: z.number().finite(),
  trade_code: z.string().optional(),
  work_party: WorkPartySchema.nullable().optional(),
  necessity: OwnerNecessitySchema.optional(),
  title: z.string().optional(),
});

export const RuleD5PayloadSchema = z.object({
  docking_context: DockingContextSchema,
  lines: z.array(RepairLineSchema).min(1),
  assume_statutory_owner_work: z.boolean().optional(),
});

export type RuleD5Payload = z.infer<typeof RuleD5PayloadSchema>;
export type RepairLinePayload = z.infer<typeof RepairLineSchema>;

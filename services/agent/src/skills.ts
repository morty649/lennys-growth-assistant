import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const skillCandidates = [
  process.env.SHIP30_SKILL_PATH,
  resolve(process.cwd(), "skills/ship-30/SKILL.md"),
  resolve(process.cwd(), "../../skills/ship-30/SKILL.md"),
].filter((path): path is string => Boolean(path));

export function loadShip30Skill(): string {
  const path = skillCandidates.find(existsSync);
  if (!path) {
    throw new Error("Ship 30 skill file is unavailable");
  }
  return readFileSync(path, "utf8").trim();
}

export function ship30SkillDescription(): string {
  const skill = loadShip30Skill();
  const description = skill.match(/^description:\s*(.+)$/m)?.[1]?.trim();
  const source = skill.match(/^source:\s*(.+)$/m)?.[1]?.trim();
  if (!description || !source) throw new Error("Ship 30 skill metadata is incomplete");
  return `${description} It produces an approximately 1,250-word Markdown essay with a strong hook, clear narrative progression, skimmable headings, selective bold emphasis, a specific takeaway, and sentence-level transcript citations. It is based on ${source}.`;
}

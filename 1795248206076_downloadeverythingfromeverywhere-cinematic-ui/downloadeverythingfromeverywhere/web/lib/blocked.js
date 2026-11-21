export const BLOCKED = [
  "m/969681",
  "m/445466",
  "m/1058424",
  "m/1263337",
  "m/1490214",
  "m/1631807",
  "s/113962",
];

export function isBlocked(kind, id) {
  return BLOCKED.includes(`${kind}/${id}`);
}

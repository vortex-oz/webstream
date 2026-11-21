import { notFound } from "next/navigation";
import { isBlocked } from "./blocked.js";

export async function or404(p, kind, id) {
  if (kind && isBlocked(kind, id)) notFound();
  try {
    return await p;
  } catch (e) {
    if (String(e?.message || e).includes("404")) notFound();
    throw e;
  }
}

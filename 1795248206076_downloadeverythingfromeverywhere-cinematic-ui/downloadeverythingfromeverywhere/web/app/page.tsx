import Search from "./Search";
import JsonLd from "./JsonLd";
import { loadTrending } from "../lib/tmdb.js";
import { HOME_TITLE, itemListJsonLd, socialMeta, SITE_DESC } from "../lib/seo.js";

export const revalidate = 3600;

export async function generateMetadata({ searchParams }) {
  const q = String((await searchParams)?.q || "").trim();
  const meta = socialMeta({
    title: { absolute: HOME_TITLE },
    description: SITE_DESC,
    path: "/",
  });
  if (q) return { ...meta, robots: { index: false, follow: true } };
  return meta;
}

export default async function Home({ searchParams }) {
  const q = String((await searchParams)?.q || "").trim();
  let trending = [];
  try {
    trending = await loadTrending(50);
  } catch {
    trending = [];
  }
  return (
    <>
      {trending.length ? <JsonLd data={itemListJsonLd(trending)} /> : null}
      <Search trending={trending} q={q} />
    </>
  );
}

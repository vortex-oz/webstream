import AnimeDownload from "../../AnimeDownload";
import JsonLd from "../../JsonLd";
import { loadAnime } from "../../../lib/tmdb.js";
import { or404 } from "../../../lib/or-404.js";
import { animeJsonLd, mediaSocialMeta } from "../../../lib/seo.js";

export const revalidate = 3600;

export async function generateMetadata({ params }) {
  const { id } = await params;
  const item = await or404(loadAnime(id), "a", id);
  return mediaSocialMeta(item, "anime", `/a/${id}`);
}

export default async function Page({ params }) {
  const { id } = await params;
  const initial = await or404(loadAnime(id), "a", id);
  return (
    <>
      <JsonLd data={animeJsonLd(initial)} />
      <AnimeDownload id={String(id)} initial={initial} />
    </>
  );
}

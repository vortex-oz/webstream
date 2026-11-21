import SeriesDownload from "../../SeriesDownload";
import JsonLd from "../../JsonLd";
import { loadTv } from "../../../lib/tmdb.js";
import { or404 } from "../../../lib/or-404.js";
import { mediaSocialMeta, tvJsonLd } from "../../../lib/seo.js";

export const revalidate = 3600;

export async function generateMetadata({ params }) {
  const { id } = await params;
  return mediaSocialMeta(await or404(loadTv(id), "s", id), "tv", `/s/${id}`);
}

export default async function Page({ params }) {
  const { id } = await params;
  const initial = await or404(loadTv(id), "s", id);
  return (
    <>
      <JsonLd data={tvJsonLd(initial)} />
      <SeriesDownload id={String(id)} initial={initial} />
    </>
  );
}

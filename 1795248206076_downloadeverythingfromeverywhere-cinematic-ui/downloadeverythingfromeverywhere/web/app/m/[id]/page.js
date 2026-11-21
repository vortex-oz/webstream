import MovieDownload from "../../MovieDownload";
import JsonLd from "../../JsonLd";
import { loadMovie } from "../../../lib/tmdb.js";
import { or404 } from "../../../lib/or-404.js";
import { mediaSocialMeta, movieJsonLd } from "../../../lib/seo.js";

export const revalidate = 3600;

export async function generateMetadata({ params }) {
  const { id } = await params;
  return mediaSocialMeta(await or404(loadMovie(id), "m", id), "movie", `/m/${id}`);
}

export default async function Page({ params }) {
  const { id } = await params;
  const initial = await or404(loadMovie(id), "m", id);
  return (
    <>
      <JsonLd data={movieJsonLd(initial)} />
      <MovieDownload id={String(id)} initial={initial} />
    </>
  );
}

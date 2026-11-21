import JsonLd from "../JsonLd";
import { socialMeta, SITE_NAME, SITE_URL, absUrl } from "../../lib/seo.js";

export const metadata = socialMeta({
  title: "How to download free movies and TV",
  description: `How to search and free download movies, TV shows & anime in 1080p, 720p & 4K on ${SITE_NAME}.`,
  path: "/guide",
});

export default function GuideLayout({ children }) {
  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: "How to download free movies and TV",
          url: absUrl("/guide"),
          isPartOf: { "@type": "WebSite", name: SITE_NAME, url: SITE_URL },
        }}
      />
      {children}
    </>
  );
}

class FallbackDownloader:
    """Retry tracks spotdl couldn't get, via a hi-fi service (Qobuz/Tidal) using streamrip."""
    def __init__(self, output_dir, log_manager, services=("qobuz", "tidal")):
        self.output_dir = Path(output_dir)
        self.log = log_manager
        self.services = services

    def recover(self, failed_items, metadata_by_url):
        """failed_items: the deduped failure dicts; metadata_by_url: {spotify_url: {isrc, artist, name}}"""
        recovered = 0
        # Only worth retrying matches that genuinely weren't found / failed to grab.
        # rate_limited ones are spotdl-retryable, not a matching problem - skip them here.
        targets = [f for f in failed_items if f["category"] in ("not_found", "download_error")]
        for item in targets:
            meta = metadata_by_url.get(item["url"], {})
            if self._search_and_download(meta.get("isrc"),
                                         f"{meta.get('artist','')} {meta.get('name','')}".strip()):
                recovered += 1
                self.log.log_success(f"[fallback] recovered via hi-fi: {item['url']}", console=False)
            else:
                self.log.log_failure(f"[fallback-miss] no hi-fi match: {item['url']}", console=False)
        return recovered

    def _search_and_download(self, isrc, query) -> bool:
        """Try each configured service until one yields a download. TOOL-SPECIFIC - the part to nail."""
        for service in self.services:
            try:
                # Resolve ISRC/query -> a track id/url on `service`, then:
                #   subprocess.run(["rip", "url", resolved_url], ...)  (streamrip)
                # or a non-interactive primitive like qobuz-dl `lucky`.
                if self._run_one(service, isrc, query):
                    return True
            except Exception as e:
                self.log.log_error(f"[fallback] {service} error for '{query}': {e}", console=False)
        return False

    def _run_one(self, service, isrc, query) -> bool:
        raise NotImplementedError  # implement per chosen tool
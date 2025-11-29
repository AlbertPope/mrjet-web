import os
import re
from typing import Optional, List, Callable

import m3u8
from pym3u8downloader import M3U8Downloader

from mrjet.logger import logger
from mrjet.request_handler import RequestHandler, CFHandler

class ProgressM3U8Downloader(M3U8Downloader):
    """Extend M3U8Downloader"""
    def __init__(self, progress_callback: Callable = None, *args, **kwargs):
        self.progress_callback = progress_callback
        self._current_stage = "Preparing"
        self._current_percent = 0
        super().__init__(*args, **kwargs)

    def _capture_progress(self, line: str):
        if self.progress_callback:
            progress = self.parse_progress_line(line)
            if progress:
                self.progress_callback(progress)

    def parse_progress_line(self, line: str) -> Optional[dict]:
        pattern = r'(\w+)\s*:\s*\[(#+)\s*\]\s*(\d+)%'
        match = re.search(pattern, line)

        if match:
            stage = match.group(1).strip()
            percent = int(match.group(3))

            stage_map = {
                'Verify': '验证中',
                'Download': '下载中',
                'Build': '合并中'
            }

            stage_cn = stage_map.get(stage, stage)

            return {
                'stage': stage_cn,
                'percent': percent,
                'raw_line': line.strip()
            }
        return None

    def download_playlist(self):
        import io
        from contextlib import redirect_stdout

        class ProgressCapture(io.StringIO):
            def write(self, text):
                super().write(text)
                if hasattr(self, '_downloader'):
                    self._downloader._capture_progress(text)

        progress_capture = ProgressCapture()
        progress_capture._downloader = self

        try:
            with redirect_stdout(progress_capture):
                super().download_playlist()
        except Exception as e:
            logger.error(f"Downloading error: {e}")
            raise

class MovieDownloader:
    def __init__(self):
        self.request_handler = RequestHandler()
        self.cf_handler = CFHandler()

    @staticmethod
    def _get_specify_variant(m3u8_list: List[str], resolution: str):
        for item in m3u8_list:
            if item.startswith(resolution):
                return item

        return m3u8_list[-1] if m3u8_list else None

    @staticmethod
    def _get_last_variant(m3u8_list: List[str]) -> Optional[str]:
        return m3u8_list[-1]

    @staticmethod
    def _get_all_variant(m3u8_content: str):
        playlist = m3u8.loads(m3u8_content)
        items = []
        if playlist.is_variant:
            for item in playlist.playlists:
                items.append(item.uri)
            return items
        else:
            return None

    @staticmethod
    def _get_uuid(html: str) -> Optional[str]:
        uuid_match = re.search(r"m3u8\|([a-f0-9|]+)\|com\|surrit\|https\|video", html)
        uuid_result = uuid_match.group(1)
        if not uuid_result:
            logger.error("Failed to extract UUID from HTML.")
            return None
        uuid = "-".join(uuid_result.split("|")[::-1])
        return uuid

    @staticmethod
    def _get_movie_id(url: str) -> Optional[str]:
        movie_id = url.split("/")[-1]
        if not movie_id:
            logger.error("Failed to extract movie ID from URL.")
            return None
        return movie_id

    def download_with_progress(self, url: str, output_dir: str, resolution: str = "", progress_callback: Callable = None) -> bool:
        """downloader with callback"""
        try:
            page_html = self.cf_handler.get(url).decode("utf-8")
            uuid = self._get_uuid(page_html)
            movie_id = self._get_movie_id(url).upper()
            m3u8_url = f"https://surrit.com/{uuid}/playlist.m3u8"
            m3u8_html = self.request_handler.get(m3u8_url).decode("utf-8")
            all_res = self._get_all_variant(m3u8_html)

            if resolution and all_res:
                res_part = self._get_specify_variant(all_res, resolution)
            else:
                res_part = self._get_last_variant(all_res) if all_res else None

            if not res_part:
                raise Exception("Can't get video stream URL")

            video_url = f"https://surrit.com/{uuid}/{res_part}"

            movie_dir = os.path.join(output_dir, movie_id)
            os.makedirs(movie_dir, exist_ok=True)
            output_path = os.path.join(movie_dir, f"{movie_id}.mp4")

            # Use downloader with progress
            downloader = ProgressM3U8Downloader(
                input_file_path = video_url,
                output_file_path = output_path,
                progress_callback = progress_callback
            )

            downloader.download_playlist()
            return downloader.is_download_complete

        except Exception as e:
            logger.error(f"Download failed: {e}")
            if progress_callback:
                progress_callback({
                    'stage': 'Failed',
                    'percent': 0,
                    'raw_line': f'Download failed: {str(e)}'
                })
            return False

    def download_specify_quality(self, url: str, output_dir: str, resolution: str):
        return self.download_with_progress(url, output_dir, resolution)

    def download_highest_quality(self, url: str, output_dir: str):
        return self.download_with_progress(url, output_dir)
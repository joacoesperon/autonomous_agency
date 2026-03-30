"""
Real social publishing helpers for the Marketer workflow.

Supported publishing paths:
- Instagram Graph API (post, story, carousel, reel)
- X API (single post, thread)
- TikTok Content Posting API (video upload/direct post)
- YouTube Shorts via YouTube Data API
- Facebook Page publishing (post, photo, video)

Notes:
- Instagram publishing requires a publicly reachable media URL. For local files,
  configure PUBLIC_MEDIA_BASE_URL so the file can be addressed from outside the
  local machine.
- YouTube uploads require OAuth client credentials and a one-time local auth
  flow on the future user's machine.
"""

from __future__ import annotations

import json
import math
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml

from shared.provider_profiles import load_brand_config


CaptionType = Union[str, List[str]]


class SocialPublisher:
    """Official-API publisher for the Marketer autopublish workflow."""

    VALID_PLATFORMS = ["instagram", "twitter", "tiktok", "youtube_shorts", "facebook"]

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.config = load_brand_config()
        self.publishing_config = self.config.get("publishing", {})

        self.instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_user_id = os.getenv("INSTAGRAM_USER_ID")

        self.twitter_api_key = os.getenv("X_API_KEY")
        self.twitter_api_secret = os.getenv("X_API_SECRET")
        self.twitter_access_token = os.getenv("X_ACCESS_TOKEN")
        self.twitter_access_secret = os.getenv("X_ACCESS_SECRET")

        self.tiktok_access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        self.youtube_client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.youtube_client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        self.youtube_token_file = (
            os.getenv("YOUTUBE_TOKEN_FILE")
            or self.publishing_config.get("youtube_shorts", {}).get("token_file")
            or str(self.project_root / "shared" / "memory" / "youtube_token.json")
        )

        self.facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.facebook_page_id = os.getenv("FACEBOOK_PAGE_ID")

        self.public_media_base_url = (
            os.getenv("PUBLIC_MEDIA_BASE_URL")
            or self.publishing_config.get("public_media_base_url")
        )

        self.instagram_api_version = (
            os.getenv("INSTAGRAM_GRAPH_API_VERSION")
            or self.publishing_config.get("instagram", {}).get("api_version")
            or "v22.0"
        )
        self.facebook_api_version = (
            os.getenv("FACEBOOK_GRAPH_API_VERSION")
            or self.publishing_config.get("facebook", {}).get("api_version")
            or "v22.0"
        )

        self.retry_attempts = max(int(self.publishing_config.get("retry_attempts", 2) or 2), 1)
        self.retry_delay_seconds = max(int(self.publishing_config.get("retry_delay_seconds", 30) or 30), 1)
        self.last_post_time: Dict[str, float] = {}

    def execute(
        self,
        platforms: List[str],
        caption: CaptionType,
        media_paths: Optional[List[str]] = None,
        content_type: str = "post",
        scheduled_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        overall_success = True

        for platform in platforms:
            if platform not in self.VALID_PLATFORMS:
                return {
                    "success": False,
                    "message": f"Invalid platform: {platform}. Use: {self.VALID_PLATFORMS}",
                }

        if content_type in {"carousel", "reel", "story"} and not media_paths:
            return {
                "success": False,
                "message": f"Content type '{content_type}' requires media_paths",
            }

        for platform in platforms:
            if not self._check_rate_limit(platform):
                results[platform] = {
                    "success": False,
                    "message": f"Rate limit exceeded for {platform}. Wait before posting again.",
                }
                overall_success = False
                continue

            result = self._publish_to_platform(
                platform=platform,
                caption=caption,
                media_paths=media_paths or [],
                content_type=content_type,
                scheduled_time=scheduled_time,
            )
            results[platform] = result
            if not result.get("success"):
                overall_success = False

        self._log_published_content(platforms, caption, content_type, results)
        return {
            "success": overall_success,
            "results": results,
            "message": "Content published successfully" if overall_success else "Some publications failed",
        }

    def publish_reel_cross_platform(self, video_path: str, caption: str) -> Dict[str, Any]:
        return self.execute(
            platforms=["instagram", "tiktok", "youtube_shorts", "facebook"],
            caption=caption,
            media_paths=[video_path],
            content_type="reel",
        )

    def publish_carousel_with_posts(
        self,
        carousel_paths: List[str],
        caption: str,
        single_image_platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        single_image_platforms = single_image_platforms or ["facebook"]
        ig_result = self.execute(
            platforms=["instagram"],
            caption=caption,
            media_paths=carousel_paths,
            content_type="carousel",
        )
        other_result = self.execute(
            platforms=single_image_platforms,
            caption=caption,
            media_paths=[carousel_paths[0]],
            content_type="post",
        )
        combined_results = {**ig_result.get("results", {}), **other_result.get("results", {})}
        return {
            "success": ig_result.get("success", False) and other_result.get("success", False),
            "results": combined_results,
            "message": "Published carousel bundle"
            if ig_result.get("success", False) and other_result.get("success", False)
            else "Some carousel bundle publications failed",
        }

    def publish_content_bundle(self, approval_record: Dict[str, Any]) -> Dict[str, Any]:
        metadata = approval_record.get("metadata") or {}
        target_platforms = metadata.get("platforms") or []
        if not target_platforms:
            target_platforms = ["instagram", "twitter", "tiktok", "youtube_shorts", "facebook"]

        caption = self._resolve_bundle_caption(approval_record)
        video_path = metadata.get("video_path") or approval_record.get("media_url")
        story_image = metadata.get("story_image")
        carousel_images = metadata.get("carousel_images") or []
        tweets = metadata.get("tweets") or []

        if not story_image and carousel_images:
            story_image = carousel_images[0]

        bundle_results: Dict[str, Any] = {}
        published_steps: List[str] = []

        if story_image and "instagram" in target_platforms:
            result = self._execute_publish_step_with_retry(
                step_name="instagram_story",
                publish_callable=lambda: self.execute(
                    platforms=["instagram"],
                    caption=caption,
                    media_paths=[story_image],
                    content_type="story",
                ),
            )
            bundle_results["instagram_story"] = result
            if result.get("success"):
                published_steps.append("instagram_story")

        video_platforms = [p for p in ["instagram", "tiktok", "youtube_shorts", "facebook"] if p in target_platforms]
        if video_path and video_platforms:
            result = self._execute_publish_step_with_retry(
                step_name="reel_bundle",
                publish_callable=lambda: self.execute(
                    platforms=video_platforms,
                    caption=caption,
                    media_paths=[video_path],
                    content_type="reel",
                ),
            )
            bundle_results["reel_bundle"] = result
            if result.get("success"):
                published_steps.append("reel_bundle")

        if tweets and "twitter" in target_platforms:
            thread_media = [carousel_images[0]] if carousel_images else None
            result = self._execute_publish_step_with_retry(
                step_name="twitter_thread",
                publish_callable=lambda: self.execute(
                    platforms=["twitter"],
                    caption=tweets,
                    media_paths=thread_media,
                    content_type="thread",
                ),
            )
            bundle_results["twitter_thread"] = result
            if result.get("success"):
                published_steps.append("twitter_thread")

        if carousel_images and "instagram" in target_platforms:
            result = self._execute_publish_step_with_retry(
                step_name="instagram_carousel",
                publish_callable=lambda: self.execute(
                    platforms=["instagram"],
                    caption=caption,
                    media_paths=carousel_images,
                    content_type="carousel",
                ),
            )
            bundle_results["instagram_carousel"] = result
            if result.get("success"):
                published_steps.append("instagram_carousel")

        overall_success = bool(bundle_results) and all(
            result.get("success") for result in bundle_results.values()
        )
        return {
            "success": overall_success,
            "published_steps": published_steps,
            "results": bundle_results,
            "message": "Content bundle published" if overall_success else "Content bundle published partially or failed",
        }

    def _execute_publish_step_with_retry(self, step_name: str, publish_callable) -> Dict[str, Any]:
        last_result: Dict[str, Any] = {"success": False, "message": f"{step_name} was not executed"}
        for attempt in range(1, self.retry_attempts + 1):
            last_result = publish_callable()
            if last_result.get("success"):
                if attempt > 1:
                    last_result["message"] = (
                        f"{last_result.get('message', step_name)} "
                        f"(succeeded on retry {attempt})"
                    )
                return last_result
            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay_seconds)
        return last_result

    def _publish_to_platform(
        self,
        platform: str,
        caption: CaptionType,
        media_paths: List[str],
        content_type: str,
        scheduled_time: Optional[str],
    ) -> Dict[str, Any]:
        try:
            if platform == "instagram":
                return self._publish_instagram(caption=str(caption), media_paths=media_paths, content_type=content_type)
            if platform == "twitter":
                if content_type == "thread":
                    if not isinstance(caption, list):
                        return {
                            "success": False,
                            "message": "Twitter thread publishing requires caption to be a list of tweets",
                        }
                    return self._publish_twitter_thread(caption, media_paths=media_paths or None)
                return self._publish_twitter(str(caption), media_path=media_paths[0] if media_paths else None)
            if platform == "tiktok":
                if content_type != "reel" or not media_paths:
                    return {"success": False, "message": "TikTok requires video content (reel type)"}
                return self._publish_tiktok(str(caption), media_paths[0])
            if platform == "youtube_shorts":
                if content_type != "reel" or not media_paths:
                    return {"success": False, "message": "YouTube Shorts requires video content (reel type)"}
                return self._publish_youtube_shorts(self._build_youtube_title(str(caption)), str(caption), media_paths[0])
            if platform == "facebook":
                return self._publish_facebook(str(caption), media_paths, content_type)
            return {"success": False, "message": f"Unsupported platform: {platform}"}
        except Exception as exc:
            return {"success": False, "message": f"{platform} publish failed: {exc}"}

    def _publish_instagram(self, caption: str, media_paths: List[str], content_type: str) -> Dict[str, Any]:
        if not self.instagram_token or not self.instagram_user_id:
            return {"success": False, "message": "Instagram access token or user ID not configured"}

        if content_type == "story":
            return self._publish_instagram_story(caption, media_paths[0] if media_paths else None)
        if content_type == "carousel":
            return self._publish_instagram_carousel(caption, media_paths)
        if content_type == "reel":
            return self._publish_instagram_reel(caption, media_paths[0] if media_paths else None)
        return self._publish_instagram_post(caption, media_paths[0] if media_paths else None)

    def _publish_instagram_post(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        if not media_path:
            return {"success": False, "message": "Instagram post requires an image path or URL"}
        media_url = self._resolve_public_media_url(media_path)
        container_id = self._create_instagram_container({"caption": caption, "image_url": media_url})
        publish_result = self._publish_instagram_container(container_id)
        return {
            "success": True,
            "post_id": publish_result.get("id"),
            "container_id": container_id,
            "media_url": media_url,
            "message": "Instagram post published",
        }

    def _publish_instagram_story(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        if not media_path:
            return {"success": False, "message": "Instagram story requires media"}
        media_url = self._resolve_public_media_url(media_path)
        mime_type, _ = mimetypes.guess_type(media_path)
        params: Dict[str, Any] = {"media_type": "STORIES"}
        if mime_type and mime_type.startswith("video"):
            params["video_url"] = media_url
        else:
            params["image_url"] = media_url
        if caption:
            params["caption"] = caption
        container_id = self._create_instagram_container(params)
        if "video_url" in params:
            self._wait_for_instagram_container(container_id)
        publish_result = self._publish_instagram_container(container_id)
        return {
            "success": True,
            "post_id": publish_result.get("id"),
            "container_id": container_id,
            "media_url": media_url,
            "message": "Instagram story published",
        }

    def _publish_instagram_carousel(self, caption: str, media_paths: List[str]) -> Dict[str, Any]:
        if len(media_paths) < 2 or len(media_paths) > 10:
            return {"success": False, "message": "Instagram carousels require 2-10 images"}

        children: List[str] = []
        resolved_urls: List[str] = []
        for media_path in media_paths:
            media_url = self._resolve_public_media_url(media_path)
            resolved_urls.append(media_url)
            child_id = self._create_instagram_container(
                {
                    "image_url": media_url,
                    "is_carousel_item": "true",
                }
            )
            children.append(child_id)

        parent_id = self._create_instagram_container(
            {
                "caption": caption,
                "media_type": "CAROUSEL",
                "children": ",".join(children),
            }
        )
        publish_result = self._publish_instagram_container(parent_id)
        return {
            "success": True,
            "post_id": publish_result.get("id"),
            "container_id": parent_id,
            "child_container_ids": children,
            "media_urls": resolved_urls,
            "message": "Instagram carousel published",
        }

    def _publish_instagram_reel(self, caption: str, video_path: Optional[str]) -> Dict[str, Any]:
        if not video_path:
            return {"success": False, "message": "Instagram Reel requires video file"}
        media_url = self._resolve_public_media_url(video_path)
        params = {
            "media_type": "REELS",
            "video_url": media_url,
            "caption": caption,
            "share_to_feed": "true",
        }
        container_id = self._create_instagram_container(params)
        self._wait_for_instagram_container(container_id)
        publish_result = self._publish_instagram_container(container_id)
        return {
            "success": True,
            "post_id": publish_result.get("id"),
            "container_id": container_id,
            "media_url": media_url,
            "message": "Instagram reel published",
        }

    def _create_instagram_container(self, params: Dict[str, Any]) -> str:
        response = requests.post(
            self._instagram_graph_url(f"{self.instagram_user_id}/media"),
            data={**params, "access_token": self.instagram_token},
            timeout=60,
        )
        payload = self._parse_json_response(response)
        container_id = payload.get("id")
        if not container_id:
            raise RuntimeError(f"Instagram container creation failed: {payload}")
        return str(container_id)

    def _wait_for_instagram_container(self, container_id: str, timeout: int = 180, poll_interval: int = 5) -> None:
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            response = requests.get(
                self._instagram_graph_url(container_id),
                params={
                    "fields": "status_code,status",
                    "access_token": self.instagram_token,
                },
                timeout=30,
            )
            payload = self._parse_json_response(response)
            status_code = str(payload.get("status_code") or payload.get("status") or "").upper()
            if not status_code or status_code in {"FINISHED", "PUBLISHED"}:
                return
            if status_code in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Instagram container {container_id} failed with status {status_code}")
            time.sleep(poll_interval)
        raise RuntimeError(f"Instagram container {container_id} did not finish processing in time")

    def _publish_instagram_container(self, container_id: str) -> Dict[str, Any]:
        response = requests.post(
            self._instagram_graph_url(f"{self.instagram_user_id}/media_publish"),
            data={
                "creation_id": container_id,
                "access_token": self.instagram_token,
            },
            timeout=60,
        )
        payload = self._parse_json_response(response)
        if not payload.get("id"):
            raise RuntimeError(f"Instagram publish failed: {payload}")
        return payload

    def _publish_twitter(self, text: str, media_path: Optional[str]) -> Dict[str, Any]:
        session = self._get_x_oauth_session()
        media_ids: List[str] = []

        if media_path:
            media_ids.append(self._upload_x_media(session, media_path))

        payload: Dict[str, Any] = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        response = session.post("https://api.x.com/2/tweets", json=payload)
        data = self._parse_json_response(response)
        tweet_data = data.get("data") or {}
        if not tweet_data.get("id"):
            raise RuntimeError(f"X create post failed: {data}")
        return {
            "success": True,
            "post_id": tweet_data["id"],
            "message": "Post published to X",
        }

    def _publish_twitter_thread(
        self,
        tweets: List[str],
        media_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        session = self._get_x_oauth_session()
        if not tweets:
            return {"success": False, "message": "Twitter thread requires at least one tweet"}

        post_ids: List[str] = []
        media_id = None
        if media_paths:
            media_id = self._upload_x_media(session, media_paths[0])

        reply_to = None
        for index, tweet in enumerate(tweets):
            payload: Dict[str, Any] = {"text": tweet}
            if reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": reply_to}
            elif media_id:
                payload["media"] = {"media_ids": [media_id]}

            response = session.post("https://api.x.com/2/tweets", json=payload)
            data = self._parse_json_response(response)
            tweet_id = (data.get("data") or {}).get("id")
            if not tweet_id:
                raise RuntimeError(f"X thread post {index + 1} failed: {data}")
            post_ids.append(tweet_id)
            reply_to = tweet_id

        return {
            "success": True,
            "post_id": post_ids[0],
            "thread_ids": post_ids,
            "message": f"Thread published to X ({len(post_ids)} posts)",
        }

    def _upload_x_media(self, session, media_path: str) -> str:
        resolved_path = self._resolve_local_path(media_path)
        if not resolved_path:
            raise RuntimeError(f"Local media file not found for X upload: {media_path}")

        mime_type, _ = mimetypes.guess_type(str(resolved_path))
        is_video = bool(mime_type and mime_type.startswith("video"))
        if is_video:
            return self._upload_x_video_chunked(session, resolved_path)

        with resolved_path.open("rb") as media_file:
            response = session.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                files={"media": media_file},
            )
        payload = self._parse_json_response(response)
        media_id = payload.get("media_id_string")
        if not media_id:
            raise RuntimeError(f"X media upload failed: {payload}")
        return str(media_id)

    def _upload_x_video_chunked(self, session, media_path: Path) -> str:
        total_bytes = media_path.stat().st_size
        init_response = session.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={
                "command": "INIT",
                "total_bytes": total_bytes,
                "media_type": mimetypes.guess_type(str(media_path))[0] or "video/mp4",
                "media_category": "tweet_video",
            },
        )
        init_payload = self._parse_json_response(init_response)
        media_id = init_payload.get("media_id_string")
        if not media_id:
            raise RuntimeError(f"X INIT video upload failed: {init_payload}")

        segment_index = 0
        chunk_size = 5 * 1024 * 1024
        with media_path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                append_response = session.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": segment_index,
                    },
                    files={"media": chunk},
                )
                self._parse_json_response(append_response, allow_empty=True)
                segment_index += 1

        finalize_response = session.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={"command": "FINALIZE", "media_id": media_id},
        )
        finalize_payload = self._parse_json_response(finalize_response)
        processing_info = finalize_payload.get("processing_info")
        if processing_info:
            self._wait_for_x_media_processing(session, media_id, processing_info)
        return str(media_id)

    def _wait_for_x_media_processing(self, session, media_id: str, processing_info: Dict[str, Any]) -> None:
        state = processing_info.get("state")
        while state in {"pending", "in_progress"}:
            check_after = max(int(processing_info.get("check_after_secs", 5)), 1)
            time.sleep(check_after)
            status_response = session.get(
                "https://upload.twitter.com/1.1/media/upload.json",
                params={"command": "STATUS", "media_id": media_id},
            )
            status_payload = self._parse_json_response(status_response)
            processing_info = status_payload.get("processing_info") or {}
            state = processing_info.get("state")
        if state and state != "succeeded":
            raise RuntimeError(f"X media processing failed for media_id {media_id}: {processing_info}")

    def _publish_tiktok(self, caption: str, video_path: str) -> Dict[str, Any]:
        if not self.tiktok_access_token:
            return {"success": False, "message": "TikTok access token not configured"}

        resolved_path = self._resolve_local_path(video_path)
        if not resolved_path:
            return {"success": False, "message": "Valid local video path required for TikTok"}

        creator_info = self._query_tiktok_creator_info()
        privacy_level = self._choose_tiktok_privacy_level(creator_info)
        video_size = resolved_path.stat().st_size
        chunk_size = min(max(int(self.publishing_config.get("tiktok", {}).get("chunk_size_bytes", 5_000_000)), 1), video_size)
        total_chunks = max(math.ceil(video_size / chunk_size), 1)

        init_payload = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": privacy_level,
                "disable_duet": self._as_bool(self.publishing_config.get("tiktok", {}).get("disable_duet", False)),
                "disable_comment": self._as_bool(self.publishing_config.get("tiktok", {}).get("disable_comment", False)),
                "disable_stitch": self._as_bool(self.publishing_config.get("tiktok", {}).get("disable_stitch", False)),
                "video_cover_timestamp_ms": int(
                    self.publishing_config.get("tiktok", {}).get("cover_timestamp_ms", 1000)
                ),
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

        init_response = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=self._tiktok_headers(),
            json=init_payload,
            timeout=60,
        )
        init_data = self._parse_json_response(init_response)
        upload_data = init_data.get("data") or {}
        publish_id = upload_data.get("publish_id")
        upload_url = upload_data.get("upload_url")
        if not publish_id or not upload_url:
            raise RuntimeError(f"TikTok init failed: {init_data}")

        self._upload_tiktok_video_file(upload_url, resolved_path, chunk_size)
        status = self._poll_tiktok_post_status(publish_id)
        return {
            "success": True,
            "post_id": publish_id,
            "publish_status": status.get("status"),
            "message": "Video uploaded to TikTok for publishing",
        }

    def _query_tiktok_creator_info(self) -> Dict[str, Any]:
        response = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
            headers=self._tiktok_headers(),
            json={},
            timeout=30,
        )
        payload = self._parse_json_response(response)
        if (payload.get("error") or {}).get("code") not in {None, "", "ok"}:
            raise RuntimeError(f"TikTok creator info query failed: {payload}")
        return payload.get("data") or {}

    def _choose_tiktok_privacy_level(self, creator_info: Dict[str, Any]) -> str:
        configured = self.publishing_config.get("tiktok", {}).get("privacy_level", "SELF_ONLY")
        allowed = creator_info.get("privacy_level_options") or []
        if configured in allowed:
            return configured
        if allowed:
            return str(allowed[0])
        return configured

    def _upload_tiktok_video_file(self, upload_url: str, media_path: Path, chunk_size: int) -> None:
        total_bytes = media_path.stat().st_size
        offset = 0
        with media_path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                end = offset + len(chunk) - 1
                response = requests.put(
                    upload_url,
                    data=chunk,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {offset}-{end}/{total_bytes}",
                    },
                    timeout=120,
                )
                response.raise_for_status()
                offset = end + 1

    def _poll_tiktok_post_status(self, publish_id: str, timeout: int = 180, poll_interval: int = 5) -> Dict[str, Any]:
        start_time = time.time()
        last_status: Dict[str, Any] = {"status": "processing"}
        while (time.time() - start_time) < timeout:
            response = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                headers=self._tiktok_headers(),
                json={"publish_id": publish_id},
                timeout=30,
            )
            payload = self._parse_json_response(response)
            error = payload.get("error") or {}
            if error.get("code") not in {None, "", "ok"}:
                raise RuntimeError(f"TikTok post status fetch failed: {payload}")

            data = payload.get("data") or {}
            status = str(data.get("status") or "").upper()
            last_status = data or last_status
            if status in {"PUBLISH_COMPLETE", "PUBLISHED", "SUCCESS"}:
                return {**last_status, "status": status}
            if status in {"FAILED", "ERROR"}:
                raise RuntimeError(f"TikTok publish failed: {payload}")
            time.sleep(poll_interval)
        return last_status

    def _publish_youtube_shorts(self, title: str, description: str, video_path: str) -> Dict[str, Any]:
        resolved_path = self._resolve_local_path(video_path)
        if not resolved_path:
            return {"success": False, "message": "Valid video path required for YouTube Shorts"}

        credentials = self._get_youtube_credentials()
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise ImportError(
                "google-api-python-client is required for YouTube publishing"
            ) from exc

        youtube = build("youtube", "v3", credentials=credentials)
        youtube_config = self.publishing_config.get("youtube_shorts", {})
        description_text = description if "#Shorts" in description else f"{description}\n\n#Shorts"
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description_text,
                    "categoryId": str(youtube_config.get("category_id", "27")),
                },
                "status": {
                    "privacyStatus": youtube_config.get("privacy_status", "private"),
                    "selfDeclaredMadeForKids": self._as_bool(
                        youtube_config.get("self_declared_made_for_kids", False)
                    ),
                },
            },
            media_body=MediaFileUpload(str(resolved_path), chunksize=-1, resumable=True),
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response.get("id")
        if not video_id:
            raise RuntimeError(f"YouTube upload did not return a video id: {response}")
        return {
            "success": True,
            "post_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "message": "Video uploaded to YouTube Shorts",
        }

    def _get_youtube_credentials(self):
        if not self.youtube_client_id or not self.youtube_client_secret:
            raise RuntimeError(
                "YouTube publishing requires YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET"
            )

        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise ImportError(
                "google-auth-oauthlib and google-api-python-client are required for YouTube publishing"
            ) from exc

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        token_path = Path(self.youtube_token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), scopes)

        if credentials and credentials.valid:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.youtube_client_id,
                        "client_secret": self.youtube_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"],
                    }
                },
                scopes,
            )
            credentials = flow.run_local_server(port=0)

        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def _publish_facebook(self, caption: str, media_paths: List[str], content_type: str) -> Dict[str, Any]:
        if not self.facebook_access_token or not self.facebook_page_id:
            return {"success": False, "message": "Facebook access token or page ID not configured"}

        if content_type == "reel" and media_paths:
            return self._publish_facebook_reel(caption, media_paths[0])
        return self._publish_facebook_post(caption, media_paths[0] if media_paths else None)

    def _publish_facebook_post(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        if not media_path:
            response = requests.post(
                self._facebook_graph_url(f"{self.facebook_page_id}/feed"),
                data={
                    "message": caption,
                    "access_token": self.facebook_access_token,
                },
                timeout=60,
            )
            payload = self._parse_json_response(response)
            post_id = payload.get("id")
            if not post_id:
                raise RuntimeError(f"Facebook post publish failed: {payload}")
            return {
                "success": True,
                "post_id": post_id,
                "message": "Facebook feed post published",
            }

        resolved_path = self._resolve_local_path(media_path)
        if not resolved_path:
            raise RuntimeError(f"Facebook media file not found: {media_path}")

        mime_type, _ = mimetypes.guess_type(str(resolved_path))
        if mime_type and mime_type.startswith("video"):
            return self._publish_facebook_reel(caption, str(resolved_path))

        with resolved_path.open("rb") as media_file:
            response = requests.post(
                self._facebook_graph_url(f"{self.facebook_page_id}/photos"),
                data={
                    "caption": caption,
                    "access_token": self.facebook_access_token,
                    "published": "true",
                },
                files={"source": media_file},
                timeout=120,
            )
        payload = self._parse_json_response(response)
        post_id = payload.get("post_id") or payload.get("id")
        if not post_id:
            raise RuntimeError(f"Facebook photo publish failed: {payload}")
        return {
            "success": True,
            "post_id": post_id,
            "message": "Facebook photo post published",
        }

    def _publish_facebook_reel(self, caption: str, video_path: str) -> Dict[str, Any]:
        resolved_path = self._resolve_local_path(video_path)
        if not resolved_path:
            return {"success": False, "message": "Valid video path required for Facebook video publishing"}

        with resolved_path.open("rb") as media_file:
            response = requests.post(
                self._facebook_graph_url(f"{self.facebook_page_id}/videos", video_domain=True),
                data={
                    "description": caption,
                    "title": self._build_youtube_title(caption),
                    "access_token": self.facebook_access_token,
                },
                files={"source": media_file},
                timeout=300,
            )
        payload = self._parse_json_response(response)
        video_id = payload.get("id")
        if not video_id:
            raise RuntimeError(f"Facebook video publish failed: {payload}")
        return {
            "success": True,
            "post_id": video_id,
            "message": "Facebook video published",
        }

    def _resolve_bundle_caption(self, approval_record: Dict[str, Any]) -> str:
        metadata = approval_record.get("metadata") or {}
        for key in ("caption", "video_caption", "post_caption", "summary_caption"):
            if metadata.get(key):
                return str(metadata[key])
        return str(approval_record.get("content") or "")[:2200]

    def _resolve_local_path(self, media_path: str) -> Optional[Path]:
        if not media_path or self._is_url(media_path):
            return None
        candidate = Path(media_path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        if candidate.exists():
            return candidate
        return None

    def _resolve_public_media_url(self, media_path: str) -> str:
        if self._is_url(media_path):
            return media_path

        local_path = self._resolve_local_path(media_path)
        if not local_path:
            raise RuntimeError(f"Could not resolve local media path: {media_path}")

        if not self.public_media_base_url:
            raise RuntimeError(
                "Instagram publishing requires PUBLIC_MEDIA_BASE_URL or direct media URLs"
            )

        try:
            relative_path = local_path.resolve().relative_to(self.project_root.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"Media path {local_path} is outside the repo root and cannot be mapped to PUBLIC_MEDIA_BASE_URL"
            ) from exc

        encoded_path = "/".join(quote(part) for part in relative_path.parts)
        return urljoin(self.public_media_base_url.rstrip("/") + "/", encoded_path)

    def _get_x_oauth_session(self):
        if not all(
            [
                self.twitter_api_key,
                self.twitter_api_secret,
                self.twitter_access_token,
                self.twitter_access_secret,
            ]
        ):
            raise RuntimeError(
                "X publishing requires X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_SECRET"
            )
        try:
            from requests_oauthlib import OAuth1Session
        except ImportError as exc:
            raise ImportError("requests-oauthlib is required for X publishing") from exc

        return OAuth1Session(
            client_key=self.twitter_api_key,
            client_secret=self.twitter_api_secret,
            resource_owner_key=self.twitter_access_token,
            resource_owner_secret=self.twitter_access_secret,
        )

    def _tiktok_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.tiktok_access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _instagram_graph_url(self, path: str) -> str:
        return f"https://graph.facebook.com/{self.instagram_api_version}/{path.lstrip('/')}"

    def _facebook_graph_url(self, path: str, video_domain: bool = False) -> str:
        host = "graph-video.facebook.com" if video_domain else "graph.facebook.com"
        return f"https://{host}/{self.facebook_api_version}/{path.lstrip('/')}"

    def _build_youtube_title(self, caption: str) -> str:
        cleaned = " ".join(caption.split())
        if "#Shorts" not in cleaned:
            cleaned = f"{cleaned} #Shorts"
        return cleaned[:100]

    def _check_rate_limit(self, platform: str) -> bool:
        current_time = time.time()
        last_post = self.last_post_time.get(platform, 0)
        min_interval = max(int(self.publishing_config.get("min_interval_seconds", 0) or 0), 0)
        if min_interval and (current_time - last_post) < min_interval:
            return False
        self.last_post_time[platform] = current_time
        return True

    def _log_published_content(
        self,
        platforms: List[str],
        caption: CaptionType,
        content_type: str,
        results: Dict[str, Any],
    ) -> None:
        log_file = self.project_root / "agents" / "marketer" / "content" / "published_log.yml"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if log_file.exists():
            with log_file.open("r", encoding="utf-8") as handle:
                log = yaml.safe_load(handle) or []
        else:
            log = []

        caption_preview = caption if isinstance(caption, str) else " | ".join(caption)
        log.append(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "platforms": platforms,
                "content_type": content_type,
                "caption": caption_preview[:180] + "..." if len(caption_preview) > 180 else caption_preview,
                "results": results,
                "success": all(item.get("success") for item in results.values()) if results else False,
            }
        )

        with log_file.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(log, handle, default_flow_style=False, sort_keys=False)

    def _parse_json_response(self, response: requests.Response, allow_empty: bool = False) -> Dict[str, Any]:
        response.raise_for_status()
        if allow_empty and not response.text.strip():
            return {}
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Non-JSON response from {response.request.method} {response.url}: {response.text[:500]}"
            ) from exc

        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if code not in {None, "", "ok"}:
                raise RuntimeError(payload)
        return payload

    def _is_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

"""
========================================================================
Video Provider Wrapper - Universal Interface
========================================================================

Unified API for multiple video generation providers.

Implemented providers:
- D-ID for talking-head avatar videos
- HeyGen for avatar, talking photo, and digital twin videos
- Google Veo for cinematic prompt-based clips
- OpenAI Sora 2 / 2 Pro for premium synced-audio generative clips

Other providers remain configurable placeholders so the workflow can be
switched from `shared/brand_config.yml` without rewriting the skills layer.
"""

import os
import time
import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from shared.provider_profiles import load_brand_config


class VideoProvider:
    """Universal video generation provider wrapper."""

    PROVIDER_ENV_VARS = {
        "d-id": "D_ID_API_KEY",
        "heygen": "HEYGEN_API_KEY",
        "openai-sora": "OPENAI_API_KEY",
        "synthesia": "SYNTHESIA_API_KEY",
        "runway": "RUNWAY_API_KEY",
        "pika": "PIKA_API_KEY",
        "veo": "GOOGLE_CLOUD_PROJECT",
    }

    DID_DEFAULT_AVATAR = {
        "presenter_id": "amy-jcwCkr1grs",
        "driver_id": "uM00QMwJ9x",
    }

    DID_DEFAULT_VOICE = {
        "type": "microsoft",
        "voice_id": "en-US-JennyNeural",
        "style": "professional",
    }

    def __init__(self, provider: Optional[str] = None):
        self.project_root = Path(__file__).resolve().parent.parent
        self.config = self._load_brand_config()
        configured_provider = self.config["video_generation"]["provider"]
        self.provider = provider or configured_provider

        if self.provider not in self.config["video_generation"]:
            raise ValueError(f"Unsupported provider in brand_config.yml: {self.provider}")

        self.provider_config = self.config["video_generation"][self.provider]

    def _load_brand_config(self) -> Dict[str, Any]:
        return load_brand_config()

    def _get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        provider_name = provider or self.provider
        env_var = self.PROVIDER_ENV_VARS.get(provider_name)
        if not env_var:
            return None
        return os.getenv(env_var)

    def _resolve_output_path(self, output_path: Optional[str], extension: str = "mp4") -> str:
        if output_path:
            resolved = Path(output_path)
            if not resolved.is_absolute():
                resolved = self.project_root / resolved
        else:
            generated_dir = self.project_root / "agents" / "marketer" / "content" / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)
            resolved = generated_dir / f"video_{int(time.time())}.{extension}"

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return str(resolved)

    def _estimate_duration(self, script: str) -> int:
        word_count = len(script.split())
        return max(15, min(60, int(word_count / 2.5) + 3))

    def _aspect_ratio_to_dimensions(self, aspect_ratio: str) -> Dict[str, int]:
        if aspect_ratio == "9:16":
            return {"width": 720, "height": 1280}
        return {"width": 1280, "height": 720}

    def _get_brand_mascot_config(self) -> Dict[str, Any]:
        mascot_config = self.config.get("brand_mascot", {})
        if isinstance(mascot_config, dict):
            return mascot_config
        return {}

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.split())

    def _guess_image_mime_type(self, path_value: str, explicit_mime_type: Optional[str] = None) -> str:
        if explicit_mime_type:
            return explicit_mime_type

        suffix = Path(path_value).suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _resolve_reference_image_entries(self, avatar_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mascot_config = self._get_brand_mascot_config()
        if not mascot_config.get("enabled"):
            return []

        raw_entries = None
        if avatar_config and avatar_config.get("reference_images"):
            raw_entries = avatar_config.get("reference_images")
        else:
            raw_entries = mascot_config.get("reference_images", [])

        entries: List[Dict[str, Any]] = []
        for item in (raw_entries or [])[:3]:
            if isinstance(item, str):
                entries.append({"path": item})
            elif isinstance(item, dict):
                entries.append(dict(item))
        return entries

    def _build_veo_reference_images(self, avatar_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mascot_config = self._get_brand_mascot_config()
        mascot_veo_config = mascot_config.get("veo", {})
        default_reference_type = mascot_veo_config.get("reference_type", "asset")
        reference_entries = self._resolve_reference_image_entries(avatar_config)

        reference_images: List[Dict[str, Any]] = []
        for entry in reference_entries:
            reference_type = entry.get("reference_type", default_reference_type)
            explicit_mime_type = entry.get("mime_type")

            if entry.get("gcs_uri"):
                gcs_uri = entry["gcs_uri"]
                reference_images.append(
                    {
                        "referenceType": reference_type,
                        "image": {
                            "gcsUri": gcs_uri,
                            "mimeType": self._guess_image_mime_type(gcs_uri, explicit_mime_type),
                        },
                    }
                )
                continue

            if not entry.get("path"):
                continue

            image_path = Path(entry["path"])
            if not image_path.is_absolute():
                image_path = self.project_root / image_path

            if not image_path.exists():
                continue

            image_bytes = image_path.read_bytes()
            reference_images.append(
                {
                    "referenceType": reference_type,
                    "image": {
                        "bytesBase64Encoded": base64.b64encode(image_bytes).decode("utf-8"),
                        "mimeType": self._guess_image_mime_type(str(image_path), explicit_mime_type),
                    },
                }
            )

        return reference_images

    def _build_veo_prompt(
        self,
        script: str,
        aspect_ratio: str,
        avatar_config: Optional[Dict[str, Any]],
        using_reference_images: bool,
    ) -> str:
        mascot_config = self._get_brand_mascot_config()
        if not mascot_config.get("enabled"):
            return script

        mascot_name = mascot_config.get("name", "the brand mascot")
        mascot_description = mascot_config.get("description", "a recognizable mascot character")
        mascot_persona = mascot_config.get("persona", "confident and expressive")
        mascot_visual_style = mascot_config.get("visual_style", "stylized character animation")
        scene_prompt = None
        if avatar_config:
            scene_prompt = avatar_config.get("scene_prompt") or avatar_config.get("scene")
        if not scene_prompt:
            scene_prompt = mascot_config.get("default_scene", "a modern fintech environment")

        allowed_environments = mascot_config.get("allowed_environments", [])
        environment_hint = ", ".join(allowed_environments[:3]) if allowed_environments else "trading-related environments"
        scene_rules = mascot_config.get("scene_rules", [])
        rule_lines = "\n".join([f"- {rule}" for rule in scene_rules])

        speaking_prompt_suffix = (
            mascot_config.get("veo", {}).get(
                "speaking_prompt_suffix",
                "The mascot is clearly talking to camera with expressive mouth movement.",
            )
        )

        ratio_hint = "vertical 9:16 social video" if aspect_ratio == "9:16" else "horizontal 16:9 video"
        normalized_script = self._normalize_text(script)
        reference_line = (
            "Keep the subject tightly consistent with the provided reference images."
            if using_reference_images
            else "Keep the mascot design highly consistent from frame to frame."
        )

        prompt = f"""
Create a polished {ratio_hint} featuring {mascot_name}.

Character:
- {mascot_description}
- Persona: {mascot_persona}
- Visual style: {mascot_visual_style}

Scene:
- {scene_prompt}
- Keep the environment connected to trading, markets, or fintech.
- Suitable environment cues: {environment_hint}

Performance:
- {speaking_prompt_suffix}
- The mascot should face the viewer clearly and remain the hero subject.
- Spoken dialogue to convey on camera: "{normalized_script}"

Consistency Rules:
{rule_lines if rule_lines else "- Keep the character recognizable and on-brand."}
- {reference_line}
- Preserve the mascot as a green trading candle with a face. Do not redesign it into a human.
""".strip()

        return prompt

    def generate(
        self,
        script: str,
        duration: Optional[int] = None,
        output_path: Optional[str] = None,
        add_subtitles: bool = True,
        aspect_ratio: str = "9:16",
        voice_config: Optional[Dict[str, Any]] = None,
        avatar_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not script or len(script.strip()) < 10:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Script too short. Minimum 10 characters required.",
            }

        resolved_duration = duration or self._estimate_duration(script)
        resolved_output_path = self._resolve_output_path(output_path)

        try:
            if self.provider == "d-id":
                return self._generate_did(
                    script=script,
                    duration=resolved_duration,
                    output_path=resolved_output_path,
                    add_subtitles=add_subtitles,
                    aspect_ratio=aspect_ratio,
                    voice_config=voice_config,
                    avatar_config=avatar_config,
                )
            if self.provider == "veo":
                return self._generate_veo(
                    script=script,
                    duration=resolved_duration,
                    output_path=resolved_output_path,
                    aspect_ratio=aspect_ratio,
                    avatar_config=avatar_config,
                )
            if self.provider == "heygen":
                return self._generate_heygen(
                    script=script,
                    duration=resolved_duration,
                    output_path=resolved_output_path,
                    aspect_ratio=aspect_ratio,
                    add_subtitles=add_subtitles,
                    voice_config=voice_config,
                    avatar_config=avatar_config,
                )
            if self.provider == "openai-sora":
                return self._generate_openai_sora(
                    script=script,
                    duration=resolved_duration,
                    output_path=resolved_output_path,
                    aspect_ratio=aspect_ratio,
                )
            if self.provider == "synthesia":
                return self._not_implemented("Synthesia", resolved_duration)
            if self.provider == "runway":
                return self._not_implemented("Runway", resolved_duration)
            if self.provider == "pika":
                return self._not_implemented("Pika", resolved_duration)

            return {
                "success": False,
                "provider": self.provider,
                "message": f"Unsupported provider: {self.provider}",
            }
        except Exception as exc:
            return {
                "success": False,
                "provider": self.provider,
                "message": f"Video generation failed ({self.provider}): {exc}",
            }

    def _generate_did(
        self,
        script: str,
        duration: int,
        output_path: str,
        add_subtitles: bool,
        aspect_ratio: str,
        voice_config: Optional[Dict[str, Any]],
        avatar_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        api_key = self._get_api_key("d-id")
        if not api_key:
            return {
                "success": False,
                "provider": self.provider,
                "message": "D_ID_API_KEY not configured",
            }

        voice_settings = dict(self.DID_DEFAULT_VOICE)
        voice_settings["voice_id"] = self.provider_config.get("voice_id", voice_settings["voice_id"])
        if voice_config:
            voice_settings.update(voice_config)

        avatar_settings = dict(self.DID_DEFAULT_AVATAR)
        avatar_settings["presenter_id"] = self.provider_config.get(
            "presenter_id", avatar_settings["presenter_id"]
        )
        if avatar_config:
            avatar_settings.update(avatar_config)

        custom_avatar_url = os.getenv("D_ID_CUSTOM_AVATAR_URL")
        if custom_avatar_url and "source_url" not in avatar_settings:
            avatar_settings["source_url"] = custom_avatar_url

        payload = {
            "script": {
                "type": "text",
                "input": script,
                "provider": voice_settings,
            },
            "config": {
                "stitch": True,
                "result_format": "mp4",
            },
        }

        if "source_url" in avatar_settings:
            payload["source_url"] = avatar_settings["source_url"]
        else:
            payload["presenter_id"] = avatar_settings["presenter_id"]
            payload["driver_id"] = avatar_settings.get("driver_id", self.DID_DEFAULT_AVATAR["driver_id"])

        if add_subtitles:
            payload["config"]["subtitles"] = True
            payload["config"]["subtitles_color"] = "#45B14F"
            payload["config"]["subtitles_background"] = "rgba(16, 16, 16, 0.8)"

        headers = {
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.d-id.com/talks",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        talk_id = result.get("id")
        if not talk_id:
            return {
                "success": False,
                "provider": self.provider,
                "message": "D-ID API did not return a talk ID",
            }

        video_url = self._wait_for_did_video(talk_id=talk_id, headers={"Authorization": f"Basic {api_key}"})
        if not video_url:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Video generation timed out after 3 minutes",
            }

        download_response = requests.get(video_url, timeout=60)
        download_response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(download_response.content)

        cost_per_minute = self.provider_config.get("cost_per_minute", 0.0)
        return {
            "success": True,
            "provider": self.provider,
            "video_url": video_url,
            "local_path": output_path,
            "script_used": script,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "subtitles_enabled": add_subtitles,
            "cost": round((duration / 60.0) * cost_per_minute, 4),
            "message": f"Video generated with D-ID and saved to {output_path}",
        }

    def _wait_for_did_video(
        self,
        talk_id: str,
        headers: Dict[str, str],
        timeout: int = 180,
        poll_interval: int = 5,
    ) -> Optional[str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(
                f"https://api.d-id.com/talks/{talk_id}",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()

            status = result.get("status")
            if status == "done":
                return result.get("result_url")
            if status == "error":
                return None

            time.sleep(poll_interval)
        return None

    def _generate_veo(
        self,
        script: str,
        duration: int,
        output_path: str,
        aspect_ratio: str,
        avatar_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            import google.auth
            from google.auth.transport.requests import Request as GoogleAuthRequest
        except ImportError as exc:
            raise ImportError(
                "google-auth is required for Veo. Run: pip install google-auth"
            ) from exc

        project_id = os.getenv(self.provider_config.get("project_env", "GOOGLE_CLOUD_PROJECT"))
        if not project_id:
            return {
                "success": False,
                "provider": self.provider,
                "message": "GOOGLE_CLOUD_PROJECT not configured for Veo",
            }

        location = self.provider_config.get("location", "us-central1")
        model = self.provider_config.get("model", "veo-3.1-generate-preview")
        endpoint_root = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/"
            f"locations/{location}/publishers/google/models/{model}"
        )

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, _ = google.auth.default(scopes=scopes)
        credentials.refresh(GoogleAuthRequest())

        reference_images = self._build_veo_reference_images(avatar_config)
        veo_prompt = self._build_veo_prompt(
            script=script,
            aspect_ratio=aspect_ratio,
            avatar_config=avatar_config,
            using_reference_images=bool(reference_images),
        )

        veo_duration = self._normalize_veo_duration(duration)
        mascot_config = self._get_brand_mascot_config()
        mascot_veo_config = mascot_config.get("veo", {})
        if (
            reference_images
            and mascot_veo_config.get("force_8s_when_using_references", True)
            and model.startswith("veo-3.1")
        ):
            veo_duration = 8
        veo_aspect_ratio = "9:16" if aspect_ratio == "9:16" else "16:9"

        parameters: Dict[str, Any] = {
            "aspectRatio": veo_aspect_ratio,
            "durationSeconds": veo_duration,
            "enhancePrompt": self.provider_config.get("enhance_prompt", True),
            "generateAudio": self.provider_config.get("generate_audio", False),
            "personGeneration": self.provider_config.get("person_generation", "allow_adult"),
            "resolution": self.provider_config.get("resolution", "720p"),
            "sampleCount": self.provider_config.get("sample_count", 1),
        }

        negative_prompt = self.provider_config.get("negative_prompt")
        if negative_prompt:
            parameters["negativePrompt"] = negative_prompt

        seed = self.provider_config.get("seed")
        if seed is not None:
            parameters["seed"] = seed

        storage_uri = self.provider_config.get("storage_uri")
        if storage_uri:
            parameters["storageUri"] = storage_uri

        instance: Dict[str, Any] = {"prompt": veo_prompt}
        if reference_images:
            instance["referenceImages"] = reference_images
        elif mascot_config.get("enabled") and mascot_veo_config.get("require_reference_images"):
            return {
                "success": False,
                "provider": self.provider,
                "message": "brand_mascot is enabled for Veo but no valid reference_images were found",
            }

        payload = {
            "instances": [instance],
            "parameters": parameters,
        }

        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        response = requests.post(
            f"{endpoint_root}:predictLongRunning",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        operation_name = response.json().get("name")
        if not operation_name:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Veo API did not return an operation name",
            }

        operation_result = self._wait_for_veo_operation(
            endpoint_root=endpoint_root,
            operation_name=operation_name,
            headers=headers,
        )
        if not operation_result:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Veo generation timed out",
            }

        videos = operation_result.get("response", {}).get("videos", [])
        if not videos:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Veo completed but returned no videos",
            }

        video_item = videos[0]
        local_path = output_path
        video_url = None

        if "bytesBase64Encoded" in video_item:
            video_bytes = base64.b64decode(video_item["bytesBase64Encoded"])
            with open(local_path, "wb") as f:
                f.write(video_bytes)
        elif "gcsUri" in video_item:
            video_url = video_item["gcsUri"]
            local_path = None
        else:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Veo response did not include downloadable bytes or a storage URI",
            }

        cost_per_minute = self.provider_config.get("cost_per_minute", 0.0)
        generated_duration = veo_duration
        duration_note = ""
        if generated_duration != duration:
            duration_note = f" Requested {duration}s, generated {generated_duration}s due to Veo limits."

        return {
            "success": True,
            "provider": self.provider,
            "video_url": video_url,
            "local_path": local_path,
            "script_used": script,
            "prompt_used": veo_prompt,
            "duration": generated_duration,
            "duration_requested": duration,
            "aspect_ratio": veo_aspect_ratio,
            "reference_images_used": len(reference_images),
            "brand_mascot_enabled": mascot_config.get("enabled", False),
            "subtitles_enabled": False,
            "cost": round((generated_duration / 60.0) * cost_per_minute, 4),
            "message": f"Video generated with Veo ({model}).{duration_note}".strip(),
        }

    def _normalize_veo_duration(self, duration: int) -> int:
        allowed = [4, 6, 8]
        if duration <= 4:
            return 4
        if duration >= 8:
            return 8
        return min(allowed, key=lambda value: abs(value - duration))

    def _wait_for_veo_operation(
        self,
        endpoint_root: str,
        operation_name: str,
        headers: Dict[str, str],
        timeout: int = 300,
        poll_interval: int = 10,
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.post(
                f"{endpoint_root}:fetchPredictOperation",
                headers=headers,
                json={"operationName": operation_name},
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("done"):
                return result
            time.sleep(poll_interval)
        return None

    def _generate_heygen(
        self,
        script: str,
        duration: int,
        output_path: str,
        aspect_ratio: str,
        add_subtitles: bool,
        voice_config: Optional[Dict[str, Any]],
        avatar_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        api_key = self._get_api_key("heygen")
        if not api_key:
            return {
                "success": False,
                "provider": self.provider,
                "message": "HEYGEN_API_KEY not configured",
            }

        resolved_avatar_config = dict(self.provider_config)
        if avatar_config:
            resolved_avatar_config.update(avatar_config)

        resolved_voice_config = {
            "voice_id": self.provider_config.get("voice_id"),
            "speed": self.provider_config.get("speed"),
            "pitch": self.provider_config.get("pitch"),
        }
        if voice_config:
            resolved_voice_config.update(voice_config)

        avatar_type = resolved_avatar_config.get("character_type", "avatar")
        character: Dict[str, Any] = {
            "type": avatar_type,
            "avatar_style": resolved_avatar_config.get("avatar_style", "normal"),
        }

        if avatar_type == "talking_photo":
            talking_photo_id = resolved_avatar_config.get("talking_photo_id")
            if not talking_photo_id:
                return {
                    "success": False,
                    "provider": self.provider,
                    "message": "HeyGen talking_photo mode requires talking_photo_id",
                }
            character["talking_photo_id"] = talking_photo_id
        else:
            avatar_id = resolved_avatar_config.get("avatar_id")
            if not avatar_id:
                return {
                    "success": False,
                    "provider": self.provider,
                    "message": "HeyGen requires avatar_id for avatar videos",
                }
            character["avatar_id"] = avatar_id

        voice_id = resolved_voice_config.get("voice_id")
        if not voice_id:
            return {
                "success": False,
                "provider": self.provider,
                "message": "HeyGen requires voice_id",
            }

        voice_payload: Dict[str, Any] = {
            "type": "text",
            "input_text": script,
            "voice_id": voice_id,
        }
        if resolved_voice_config.get("speed") is not None:
            voice_payload["speed"] = resolved_voice_config["speed"]
        if resolved_voice_config.get("pitch") is not None:
            voice_payload["pitch"] = resolved_voice_config["pitch"]

        video_input: Dict[str, Any] = {
            "character": character,
            "voice": voice_payload,
        }

        background_type = resolved_avatar_config.get("background_type")
        background_value = resolved_avatar_config.get("background_value")
        background_asset_id = resolved_avatar_config.get("background_asset_id")
        background_url = resolved_avatar_config.get("background_url")
        if background_type == "color" and background_value:
            video_input["background"] = {"type": "color", "value": background_value}
        elif background_type == "image":
            background: Dict[str, Any] = {"type": "image"}
            if background_asset_id:
                background["image_asset_id"] = background_asset_id
            elif background_url:
                background["url"] = background_url
            if len(background) > 1:
                video_input["background"] = background

        payload: Dict[str, Any] = {
            "video_inputs": [video_input],
            "dimension": self._aspect_ratio_to_dimensions(aspect_ratio),
            "caption": bool(resolved_avatar_config.get("caption", add_subtitles)),
            "test": resolved_avatar_config.get("test", False),
        }

        title = resolved_avatar_config.get("title")
        if title:
            payload["title"] = title

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        video_id = result.get("data", {}).get("video_id")
        if not video_id:
            return {
                "success": False,
                "provider": self.provider,
                "message": f"HeyGen API did not return a video_id: {result}",
            }

        status_result = self._wait_for_heygen_video(video_id=video_id, headers={"X-Api-Key": api_key})
        if not status_result:
            return {
                "success": False,
                "provider": self.provider,
                "message": "HeyGen generation timed out",
            }

        status_data = status_result.get("data", {})
        status = status_data.get("status")
        if status != "completed":
            error = status_data.get("error")
            return {
                "success": False,
                "provider": self.provider,
                "message": f"HeyGen generation failed with status {status}: {error}",
            }

        video_url = status_data.get("video_url")
        if not video_url:
            return {
                "success": False,
                "provider": self.provider,
                "message": "HeyGen completed but returned no video_url",
            }

        download_response = requests.get(video_url, timeout=120)
        download_response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(download_response.content)

        resolved_duration = status_data.get("duration") or duration
        cost_per_minute = self.provider_config.get("cost_per_minute", 0.0)
        return {
            "success": True,
            "provider": self.provider,
            "video_id": video_id,
            "video_url": video_url,
            "local_path": output_path,
            "script_used": script,
            "duration": resolved_duration,
            "duration_requested": duration,
            "aspect_ratio": aspect_ratio,
            "subtitles_enabled": bool(payload.get("caption")),
            "thumbnail_url": status_data.get("thumbnail_url"),
            "cost": round((float(resolved_duration) / 60.0) * cost_per_minute, 4),
            "message": f"Video generated with HeyGen and saved to {output_path}",
        }

    def _generate_openai_sora(
        self,
        script: str,
        duration: int,
        output_path: str,
        aspect_ratio: str,
    ) -> Dict[str, Any]:
        api_key = self._get_api_key("openai-sora")
        if not api_key:
            return {
                "success": False,
                "provider": self.provider,
                "message": "OPENAI_API_KEY not configured",
            }

        model = self.provider_config.get("model", "sora-2")
        size = self.provider_config.get("size")
        if not size:
            size = "720x1280" if aspect_ratio == "9:16" else "1280x720"

        prompt = script.strip()
        audio_instruction = self.provider_config.get(
            "audio_instruction",
            "Generate natural synced audio that matches the narration and scene pacing.",
        )
        if audio_instruction:
            prompt = f"{prompt}\n\n{audio_instruction}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "seconds": duration,
            "size": size,
        }
        if self.provider_config.get("fps"):
            payload["fps"] = self.provider_config["fps"]
        if self.provider_config.get("background"):
            payload["background"] = self.provider_config["background"]

        response = requests.post(
            "https://api.openai.com/v1/videos",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        video_id = result.get("id")
        if not video_id:
            raise ValueError(f"OpenAI video API did not return an id: {json.dumps(result)[:400]}")

        status_result = self._wait_for_openai_video(video_id=video_id, headers=headers)
        if not status_result:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Sora generation timed out after 10 minutes",
            }

        status = status_result.get("status")
        if status != "completed":
            error_message = status_result.get("error", {}).get("message") or status_result.get("status", "unknown")
            return {
                "success": False,
                "provider": self.provider,
                "message": f"Sora generation failed: {error_message}",
            }

        content_response = requests.get(
            f"https://api.openai.com/v1/videos/{video_id}/content",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )
        content_response.raise_for_status()
        content_type = content_response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            payload = content_response.json()
            download_url = payload.get("url") or payload.get("download_url")
            if not download_url:
                raise ValueError("OpenAI video content endpoint returned JSON without a download URL")
            download_response = requests.get(download_url, timeout=120)
            download_response.raise_for_status()
            binary_content = download_response.content
        else:
            binary_content = content_response.content

        with open(output_path, "wb") as f:
            f.write(binary_content)

        cost_per_second = self.provider_config.get("cost_per_second", 0.0)
        return {
            "success": True,
            "provider": self.provider,
            "video_id": video_id,
            "local_path": output_path,
            "script_used": script,
            "prompt_used": prompt,
            "model": model,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "size": size,
            "cost": round(float(duration) * float(cost_per_second), 4),
            "message": f"Video generated with {model} and saved to {output_path}",
        }

    def _wait_for_openai_video(
        self,
        video_id: str,
        headers: Dict[str, str],
        timeout: int = 600,
        poll_interval: int = 5,
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(
                f"https://api.openai.com/v1/videos/{video_id}",
                headers={"Authorization": headers["Authorization"]},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            status = result.get("status")
            if status in {"completed", "failed", "cancelled"}:
                return result
            time.sleep(poll_interval)
        return None

    def _wait_for_heygen_video(
        self,
        video_id: str,
        headers: Dict[str, str],
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(
                "https://api.heygen.com/v1/video_status.get",
                headers=headers,
                params={"video_id": video_id},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            status = result.get("data", {}).get("status")
            if status == "completed":
                return result
            if status == "failed":
                return result
            time.sleep(poll_interval)
        return None

    def _not_implemented(self, provider_label: str, duration: int) -> Dict[str, Any]:
        env_var = self.PROVIDER_ENV_VARS.get(self.provider, "API key")
        return {
            "success": False,
            "provider": self.provider,
            "cost": round((duration / 60.0) * self.provider_config.get("cost_per_minute", 0.0), 4),
            "message": (
                f"{provider_label} is configurable in shared/brand_config.yml but its API integration "
                f"is not implemented yet. Configure {env_var} after adding the provider-specific client."
            ),
        }

    def get_provider_info(self) -> Dict[str, Any]:
        env_var = self.PROVIDER_ENV_VARS.get(self.provider)
        if self.provider == "veo":
            env_var = self.provider_config.get("project_env", "GOOGLE_CLOUD_PROJECT")
        if self.provider == "openai-sora":
            cost_value = round(float(self.provider_config.get("cost_per_second", 0.0)) * 60.0, 4)
        else:
            cost_value = self.provider_config.get("cost_per_minute", 0)
        return {
            "provider": self.provider,
            "cost_per_minute": cost_value,
            "notes": self.provider_config.get("notes", ""),
            "config": self.provider_config,
            "api_key_env": env_var,
            "api_key_configured": bool(os.getenv(env_var)) if env_var else False,
        }


def create_video_provider(provider: Optional[str] = None) -> VideoProvider:
    return VideoProvider(provider=provider)


if __name__ == "__main__":
    print("Testing Video Provider Wrapper")
    print("=" * 70)

    video = VideoProvider()
    info = video.get_provider_info()
    print(f"Provider: {info['provider']}")
    print(f"API env var: {info['api_key_env']}")
    print(f"Configured: {info['api_key_configured']}")
    print(f"Notes: {info['notes']}")

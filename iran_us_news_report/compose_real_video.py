#!/usr/bin/env python3
"""
Compose REAL motion news report:
- LivePortrait-animated female anchor (continuous video, not GIF stills)
- Smooth interpolated 3D B-roll
- Female neural VO
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio_anchor"
BROLL = ROOT / "broll_smooth"
TALK = ROOT / "talking_raw"
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
OUTPUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FPS = 30
RED = (196, 30, 58)
GOLD = (212, 175, 55)
WHITE = (245, 247, 250)
MUTED = (160, 175, 195)
CYAN = (64, 196, 220)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def chrome_overlay(headline: str, sub: str) -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, 0, W, 64], fill=(8, 16, 36, 210))
    d.rectangle([0, 64, W, 68], fill=GOLD + (255,))
    d.rounded_rectangle([28, 14, 120, 50], radius=6, fill=RED + (255,))
    d.text((48, 20), "LIVE", font=font(22, True), fill=WHITE + (255,))
    d.text((140, 18), "WORLD DESK  ·  SPECIAL REPORT", font=font(22, True), fill=WHITE + (255,))

    top = H - 200
    d.rectangle([0, top, W, H - 56], fill=(8, 16, 36, 225))
    d.rectangle([0, top, 10, H - 56], fill=RED + (255,))
    d.rectangle([0, top, W, top + 3], fill=GOLD + (255,))
    d.text((36, top + 22), headline, font=font(40, True), fill=WHITE + (255,))
    d.text((36, top + 82), sub, font=font(24), fill=MUTED + (255,))

    d.rectangle([0, H - 56, W, H], fill=(4, 10, 28, 255))
    d.rectangle([0, H - 56, W, H - 52], fill=CYAN + (255,))
    d.text(
        (28, H - 40),
        "IRAN–U.S.  ·  Mutual strike pause Day 2  ·  Hormuz shipping low  ·  Oman mediation",
        font=font(20),
        fill=WHITE + (255,),
    )
    return overlay


def apply_chrome(clip: VideoFileClip, headline: str, sub: str):
    overlay_img = chrome_overlay(headline, sub)
    overlay_clip = ImageClip(np.array(overlay_img)).with_duration(clip.duration).with_fps(FPS)
    base = clip.resized((W, H))
    return CompositeVideoClip([base, overlay_clip], size=(W, H))


def loop_to_duration(clip: VideoFileClip, duration: float) -> VideoFileClip:
    if clip.duration >= duration:
        return clip.subclipped(0, duration)
    n = int(duration / clip.duration) + 1
    parts = [clip] * n
    looped = concatenate_videoclips(parts)
    return looped.subclipped(0, duration)


SEGMENTS = [
    {
        "id": "open",
        "kind": "anchor",
        "headline": "Iran–U.S. Conflict: Situation Briefing",
        "sub": "World Desk  ·  27 July 2026",
    },
    {
        "id": "map",
        "kind": "map",
        "headline": "Strait of Hormuz: The Strategic Flashpoint",
        "sub": "Shipping at a three-week low  ·  U.S. naval blockade remains in effect",
    },
    {
        "id": "escalation",
        "kind": "anchor",
        "headline": "Two Weeks of Escalation",
        "sub": "Nightly strikes  ·  Regional retaliation  ·  Contested shipping lanes",
    },
    {
        "id": "timeline",
        "kind": "timeline",
        "headline": "Five Months of Conflict",
        "sub": "Late February outbreak  →  June interim deal  →  July Hormuz surge  →  Strike pause",
    },
    {
        "id": "diplomacy",
        "kind": "anchor",
        "headline": "Oman Mediation & the Pause",
        "sub": "Talks underway  ·  Conditional halt in strikes",
    },
    {
        "id": "outlook",
        "kind": "anchor",
        "headline": "Fragile Calm, Unresolved Stakes",
        "sub": "Blockade continues  ·  Markets watching Hormuz",
    },
]


def find_anchor_video() -> Path:
    candidates = sorted(TALK.glob("anchor_studio*.mp4")) + sorted(TALK.glob("anchor--*.mp4"))
    # Prefer non-concat pasteback animated video
    preferred = [p for p in candidates if "concat" not in p.name and p.stat().st_size > 100_000]
    if preferred:
        # longest / newest
        preferred.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return preferred[0]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(f"No LivePortrait output in {TALK}")


def build():
    anchor_path = find_anchor_video()
    print("Using anchor video:", anchor_path)
    anchor_src = VideoFileClip(str(anchor_path))

    map_path = BROLL / "map3d_smooth.mp4"
    tl_path = BROLL / "timeline3d_smooth.mp4"
    if not map_path.exists() or not tl_path.exists():
        raise SystemExit("Missing smooth B-roll videos")

    clips = []
    for seg in SEGMENTS:
        audio = AudioFileClip(str(AUDIO / f"{seg['id']}.wav"))
        dur = audio.duration + 0.25
        print(f"{seg['id']}: {seg['kind']} {dur:.1f}s")

        if seg["kind"] == "anchor":
            # Phase offset so each segment starts at different motion
            phase = {"open": 0.0, "escalation": 4.5, "diplomacy": 9.0, "outlook": 13.5}.get(seg["id"], 0.0)
            # Rotate start within source
            start = phase % max(anchor_src.duration - 0.5, 0.1)
            piece = anchor_src.subclipped(start, anchor_src.duration)
            looped = loop_to_duration(piece, dur)
            # If still short because of edge, loop full
            if looped.duration < dur - 0.05:
                looped = loop_to_duration(anchor_src, dur)
            visual = apply_chrome(looped.without_audio(), seg["headline"], seg["sub"]).with_audio(audio)
            clips.append(visual)
        elif seg["kind"] == "map":
            broll = VideoFileClip(str(map_path))
            looped = loop_to_duration(broll.without_audio(), dur)
            visual = apply_chrome(looped, seg["headline"], seg["sub"]).with_audio(audio)
            clips.append(visual)
        elif seg["kind"] == "timeline":
            broll = VideoFileClip(str(tl_path))
            looped = loop_to_duration(broll.without_audio(), dur)
            visual = apply_chrome(looped, seg["headline"], seg["sub"]).with_audio(audio)
            clips.append(visual)

    final = concatenate_videoclips(clips, method="compose")
    out = OUTPUT / "Iran_US_War_News_Report_RealVideo.mp4"
    print("Writing", out)
    final.write_videofile(
        str(out),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="5000k",
        audio_bitrate="192k",
        threads=4,
        logger="bar",
    )
    final.close()
    anchor_src.close()

    iphone = OUTPUT / "Iran_US_War_News_Report_RealVideo_iPhone.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(out),
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart",
            str(iphone),
        ],
        check=True,
    )
    print("DONE", out)
    print("IPHONE", iphone)
    return out, iphone


if __name__ == "__main__":
    build()

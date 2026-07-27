#!/usr/bin/env python3
"""
Iran–U.S. news report with female studio anchor (hybrid performance).
Female neural TTS + pose-keyframed A-roll over virtual newsroom,
intercut with existing 3D situation B-roll.
"""

from __future__ import annotations

import asyncio
import math
import os
import subprocess
from pathlib import Path

import edge_tts
import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
ANCHOR_DIR = ASSETS / "anchor"
STUDIO_DIR = ASSETS / "studio"
AUDIO = ROOT / "audio_anchor"
FRAMES = ROOT / "frames"
OUTPUT = ROOT / "output"
for d in (AUDIO, OUTPUT):
    d.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FPS = 30
VOICE = "en-US-AvaNeural"  # professional female news voice

RED = (196, 30, 58)
GOLD = (212, 175, 55)
WHITE = (245, 247, 250)
MUTED = (160, 175, 195)
CYAN = (64, 196, 220)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


POSE_FILES = {
    "smile": "anchor_pose_smile.png",
    "blink": "anchor_pose_speak_blink.png",
    "nod": "anchor_pose_nod.png",
    "gesture_r": "anchor_pose_gesture_right.png",
    "gesture_l": "anchor_pose_gesture_left.png",
    "neutral": "anchor_pose_neutral.png",
}


def load_pose(name: str) -> Image.Image:
    path = ANCHOR_DIR / POSE_FILES[name]
    img = Image.open(path).convert("RGB")
    return img.resize((W, H), Image.Resampling.LANCZOS)


def draw_broadcast_chrome(img: Image.Image, headline: str, sub: str, live: bool = True) -> Image.Image:
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Top breaking bar
    d.rectangle([0, 0, W, 64], fill=(8, 16, 36, 210))
    d.rectangle([0, 64, W, 68], fill=GOLD + (255,))
    if live:
        d.rounded_rectangle([28, 14, 120, 50], radius=6, fill=RED + (255,))
        d.text((48, 20), "LIVE", font=font(22, True), fill=WHITE + (255,))
        d.text((140, 18), "WORLD DESK  ·  SPECIAL REPORT", font=font(22, True), fill=WHITE + (255,))
    else:
        d.text((36, 18), "WORLD DESK  ·  SPECIAL REPORT", font=font(22, True), fill=WHITE + (255,))

    # Lower third
    top = H - 200
    d.rectangle([0, top, W, H - 56], fill=(8, 16, 36, 225))
    d.rectangle([0, top, 10, H - 56], fill=RED + (255,))
    d.rectangle([0, top, W, top + 3], fill=GOLD + (255,))
    d.text((36, top + 22), headline, font=font(40, True), fill=WHITE + (255,))
    d.text((36, top + 82), sub, font=font(24), fill=MUTED + (255,))

    # Ticker
    d.rectangle([0, H - 56, W, H], fill=(4, 10, 28, 255))
    d.rectangle([0, H - 56, W, H - 52], fill=CYAN + (255,))
    d.text(
        (28, H - 40),
        "IRAN–U.S.  ·  Mutual strike pause Day 2  ·  Hormuz shipping low  ·  Oman mediation",
        font=font(20),
        fill=WHITE + (255,),
    )
    return Image.alpha_composite(base, overlay).convert("RGB")


def ken_burns_frame(base: Image.Image, t: float, duration: float, zoom_amp: float = 0.028) -> Image.Image:
    """Subtle zoom + drift for presence."""
    progress = t / max(duration, 0.001)
    zoom = 1.0 + zoom_amp * progress
    # slight horizontal drift
    drift = 8 * math.sin(progress * math.pi)
    nw, nh = int(W * zoom), int(H * zoom)
    resized = base.resize((nw, nh), Image.Resampling.LANCZOS)
    left = int((nw - W) / 2 + drift)
    top = int((nh - H) / 2 - 4 * progress)
    left = max(0, min(left, nw - W))
    top = max(0, min(top, nh - H))
    return resized.crop((left, top, left + W, top + H))


def pose_schedule(t: float, duration: float, mode: str) -> str:
    """Map time to pose name for natural gesture rhythm."""
    # Opening: smile first ~1.2s then speak cycle
    if mode == "open":
        if t < 1.3:
            return "smile"
        cycle = (t - 1.3) % 5.2
        if cycle < 1.1:
            return "blink"
        if cycle < 2.2:
            return "neutral"
        if cycle < 3.4:
            return "nod"
        if cycle < 4.3:
            return "gesture_r"
        return "blink"

    if mode == "gesture_heavy":
        cycle = t % 4.8
        if cycle < 1.0:
            return "blink"
        if cycle < 2.1:
            return "gesture_r"
        if cycle < 3.1:
            return "nod"
        if cycle < 4.0:
            return "gesture_l"
        return "neutral"

    if mode == "close":
        if t > duration - 1.4:
            return "smile"
        cycle = t % 4.5
        if cycle < 1.2:
            return "blink"
        if cycle < 2.3:
            return "nod"
        if cycle < 3.4:
            return "gesture_r"
        return "neutral"

    # default speaking
    cycle = t % 4.6
    if cycle < 1.0:
        return "blink"
    if cycle < 2.0:
        return "neutral"
    if cycle < 3.0:
        return "nod"
    if cycle < 3.8:
        return "gesture_r"
    return "blink"


def make_anchor_clip(
    duration: float,
    headline: str,
    sub: str,
    mode: str = "speak",
    audio_path: Path | None = None,
):
    poses = {k: load_pose(k) for k in POSE_FILES}
    # Pre-chrome a few poses for speed
    chromed = {k: draw_broadcast_chrome(v, headline, sub) for k, v in poses.items()}

    def make_frame(t):
        name = pose_schedule(t, duration, mode)
        # Crossfade toward next pose near boundaries for smoother motion
        frame = ken_burns_frame(chromed[name], t, duration)
        # Micro brightness pulse to suggest life/lighting
        pulse = 1.0 + 0.012 * math.sin(t * 2.2)
        arr = np.array(frame).astype(np.float32) * pulse
        return np.clip(arr, 0, 255).astype(np.uint8)

    clip = VideoClip(make_frame, duration=duration).with_fps(FPS)
    if audio_path is not None:
        audio = AudioFileClip(str(audio_path))
        clip = clip.with_audio(audio)
    return clip


def make_map_still_overlay(
    frame_path: Path,
    headline: str,
    sub: str,
    banner: str,
) -> Image.Image:
    base = Image.open(frame_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, 0, W, 90], fill=(8, 16, 36, 200))
    d.text((36, 28), banner, font=font(24, True), fill=WHITE + (255,))
    composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    return draw_broadcast_chrome(composed, headline, sub, live=True)


def frames_to_clip(frame_paths: list[Path], duration: float, headline: str, sub: str, banner: str):
    n = len(frame_paths)
    frame_dur = duration / n
    clips = []
    for fp in frame_paths:
        img = make_map_still_overlay(fp, headline, sub, banner)
        # Save temp array via ImageClip from numpy
        clips.append(ImageClip(np.array(img)).with_duration(frame_dur))
    return concatenate_videoclips(clips, method="compose")


SEGMENTS = [
    {
        "id": "open",
        "kind": "anchor",
        "mode": "open",
        "headline": "Iran–U.S. Conflict: Situation Briefing",
        "sub": "World Desk  ·  27 July 2026",
        "narration": (
            "Good evening. This is a World Desk special report. "
            "As of July twenty-seventh, twenty twenty-six, the United States and Iran have paused "
            "military strikes for a second consecutive day, opening a fragile window for diplomacy "
            "after nearly two weeks of intensifying exchanges."
        ),
    },
    {
        "id": "map",
        "kind": "map3d",
        "headline": "Strait of Hormuz: The Strategic Flashpoint",
        "sub": "Shipping at a three-week low  ·  U.S. naval blockade remains in effect",
        "banner": "3D SITUATION MAP  ·  PERSIAN GULF / STRAIT OF HORMUZ",
        "narration": (
            "At the center of the crisis is the Strait of Hormuz, the narrow waterway between Iran and Oman "
            "that, before the war, carried roughly twenty percent of the world's oil and gas exports. "
            "Commercial shipping traffic is now at a three-week low. The U.S. military says its naval blockade "
            "of Iran remains in full effect. Iran continues to assert control over passage under a mid-June interim understanding."
        ),
    },
    {
        "id": "escalation",
        "kind": "anchor",
        "mode": "gesture_heavy",
        "headline": "Two Weeks of Escalation",
        "sub": "Nightly strikes  ·  Regional retaliation  ·  Contested shipping lanes",
        "narration": (
            "The latest surge followed Iranian fire at ships trying to transit Hormuz. "
            "For about thirteen nights, U.S. forces struck Iranian coastal targets and infrastructure. "
            "Iran answered with strikes on neighboring countries hosting American bases, "
            "including sites in Kuwait, Bahrain, and Jordan, with deaths reported among service members."
        ),
    },
    {
        "id": "timeline",
        "kind": "timeline3d",
        "headline": "Five Months of Conflict",
        "sub": "Late February outbreak  →  June interim deal  →  July Hormuz surge  →  Strike pause",
        "banner": "3D CONFLICT TIMELINE  ·  FEB–JUL 2026",
        "narration": (
            "The wider war dates to late February, when the United States and Israel began military operations against Iran. "
            "A sixty-day interim deal signed in mid-June briefly eased fighting, but major issues—especially Iran's nuclear program—"
            "were deferred. That arrangement frayed as disputes over Hormuz navigation returned to the center of the conflict."
        ),
    },
    {
        "id": "diplomacy",
        "kind": "anchor",
        "mode": "speak",
        "headline": "Oman Mediation & the Pause",
        "sub": "Talks underway  ·  Conditional halt in strikes",
        "narration": (
            "U.S. Ambassador to the United Nations Mike Waltz said President Trump is giving talks room to work, "
            "with Oman and other negotiators engaged at senior and technical levels. "
            "Iran's Foreign Ministry said talks with Oman on safe passage through Hormuz made progress. "
            "A senior Iranian official told Reuters Tehran will halt its own attacks as long as Washington does the same."
        ),
    },
    {
        "id": "outlook",
        "kind": "anchor",
        "mode": "close",
        "headline": "Fragile Calm, Unresolved Stakes",
        "sub": "Blockade continues  ·  Markets watching Hormuz",
        "narration": (
            "The calm remains fragile. The U.S. blockade continues, while Iranian-backed Houthi forces have raised pressure "
            "around the Bab al-Mandeb strait. Israeli Prime Minister Benjamin Netanyahu is expected to meet President Trump "
            "in Washington on Tuesday. Global energy markets remain on edge as gasoline prices have risen again. "
            "For World Desk, I'm reporting tonight from the newsroom. Thank you for watching."
        ),
    },
]


async def synthesize(text: str, out_wav: Path, voice: str = VOICE) -> Path:
    mp3 = out_wav.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(mp3))
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(mp3),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out_wav


def load_frames(dir_path: Path) -> list[Path]:
    return sorted(dir_path.glob("frame_*.png"))


async def build():
    print("=== Female neural TTS ===")
    audio_paths = {}
    for seg in SEGMENTS:
        wav = AUDIO / f"{seg['id']}.wav"
        print(f"  {VOICE}: {seg['id']}")
        audio_paths[seg["id"]] = await synthesize(seg["narration"], wav)

    map_frames = load_frames(FRAMES / "map3d")
    tl_frames = load_frames(FRAMES / "timeline3d")
    if not map_frames or not tl_frames:
        raise SystemExit("Missing 3D frames. Run generate_report.py first to render map/timeline.")

    print("=== Composing anchor + B-roll ===")
    clips = []
    for seg in SEGMENTS:
        ap = audio_paths[seg["id"]]
        audio = AudioFileClip(str(ap))
        dur = audio.duration + 0.35

        if seg["kind"] == "anchor":
            print(f"  A-roll: {seg['id']} ({dur:.1f}s)")
            clip = make_anchor_clip(
                duration=dur,
                headline=seg["headline"],
                sub=seg["sub"],
                mode=seg.get("mode", "speak"),
                audio_path=ap,
            )
            clips.append(clip)
        elif seg["kind"] == "map3d":
            print(f"  B-roll map: {seg['id']} ({dur:.1f}s)")
            clip = frames_to_clip(
                map_frames, dur, seg["headline"], seg["sub"], seg["banner"]
            ).with_audio(audio)
            clips.append(clip)
        elif seg["kind"] == "timeline3d":
            print(f"  B-roll timeline: {seg['id']} ({dur:.1f}s)")
            clip = frames_to_clip(
                tl_frames, dur, seg["headline"], seg["sub"], seg["banner"]
            ).with_audio(audio)
            clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    out_path = OUTPUT / "Iran_US_War_News_Report_Anchor_27Jul2026.mp4"
    print(f"=== Writing {out_path} ===")
    final.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="7000k",
        audio_bitrate="192k",
        threads=4,
        logger="bar",
    )
    final.close()

    # iPhone faststart copy
    iphone = OUTPUT / "Iran_US_War_News_Report_Anchor_iPhone.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(out_path),
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart",
            str(iphone),
        ],
        check=True,
    )
    print("DONE:", out_path)
    print("IPHONE:", iphone)
    return out_path, iphone


if __name__ == "__main__":
    asyncio.run(build())

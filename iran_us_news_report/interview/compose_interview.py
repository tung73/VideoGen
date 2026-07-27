#!/usr/bin/env python3
"""Compose a ~2-minute realistic street interview video."""

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
)
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
TALK = ROOT / "talking"
OUT = ROOT / "output"
ASSETS = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FPS = 30


def font(size: int, bold: bool = False):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def lower_third(name: str, title: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # top badge
    d.rectangle([0, 0, W, 56], fill=(10, 14, 22, 200))
    d.rounded_rectangle([28, 12, 210, 44], radius=5, fill=(196, 30, 58, 255))
    d.text((48, 16), "STREET VOICE", font=font(18, True), fill=(255, 255, 255, 255))
    d.text((230, 16), "CAMPUS INTERVIEW", font=font(18, True), fill=(230, 235, 240, 255))

    top = H - 170
    d.rectangle([0, top, 720, H - 48], fill=(10, 14, 22, 230))
    d.rectangle([0, top, 8, H - 48], fill=(196, 30, 58, 255))
    d.text((28, top + 28), name, font=font(36, True), fill=(255, 255, 255, 255))
    d.text((28, top + 82), title, font=font(22), fill=(180, 190, 205, 255))

    d.rectangle([0, H - 48, W, H], fill=(8, 10, 16, 255))
    d.text(
        (24, H - 34),
        "AI on Campus  ·  How students really use ChatGPT and study tools",
        font=font(18),
        fill=(220, 225, 230, 255),
    )
    return img


def find_talking(prefix: str) -> Path:
    cands = sorted(TALK.glob(f"{prefix}*.mp4"))
    cands = [p for p in cands if "concat" not in p.name and p.stat().st_size > 50_000]
    if not cands:
        raise FileNotFoundError(prefix)
    return max(cands, key=lambda p: p.stat().st_mtime)


def loop_clip(clip: VideoFileClip, duration: float) -> VideoFileClip:
    if clip.duration >= duration:
        return clip.subclipped(0, duration)
    n = int(duration / clip.duration) + 1
    return concatenate_videoclips([clip] * n).subclipped(0, duration)


def speaker_clip(video: VideoFileClip, audio_path: Path, name: str, title: str, phase: float = 0.0):
    audio = AudioFileClip(str(audio_path))
    dur = audio.duration + 0.2
    start = phase % max(video.duration - 0.4, 0.1)
    piece = video.subclipped(start, video.duration)
    vis = loop_clip(piece.without_audio(), dur).resized((W, H))
    overlay = ImageClip(np.array(lower_third(name, title))).with_duration(dur)
    return CompositeVideoClip([vis, overlay], size=(W, H)).with_audio(audio)


SEGMENTS = [
    ("r_intro", "reporter", "Maya Chen", "Campus Voice Reporter", 0.0),
    ("s_hello", "student", "Jordan Lee", "CS Junior, State University", 1.0),
    ("r_q1", "reporter", "Maya Chen", "Campus Voice Reporter", 3.0),
    ("s_a1", "student", "Jordan Lee", "CS Junior, State University", 2.5),
    ("r_q2", "reporter", "Maya Chen", "Campus Voice Reporter", 6.0),
    ("s_a2", "student", "Jordan Lee", "CS Junior, State University", 5.0),
    ("r_q3", "reporter", "Maya Chen", "Campus Voice Reporter", 9.0),
    ("s_a3", "student", "Jordan Lee", "CS Junior, State University", 8.0),
    ("r_close", "reporter", "Maya Chen", "Campus Voice Reporter", 11.0),
]


def build():
    reporter = VideoFileClip(str(find_talking("interview_reporter")))
    student = VideoFileClip(str(find_talking("interview_student")))
    print("reporter", reporter.duration, "student", student.duration)

    clips = []
    for sid, who, name, title, phase in SEGMENTS:
        src = reporter if who == "reporter" else student
        print("seg", sid, who)
        clips.append(speaker_clip(src, AUDIO / f"{sid}.wav", name, title, phase))

    # Add brief establishing still at start from reporter image (0.8s) with soft fade feel
    still = ImageClip(str(ASSETS / "interview_reporter.png")).resized((W, H)).with_duration(0.9)
    badge = ImageClip(np.array(lower_third("Campus Voice", "Street Interview"))).with_duration(0.9)
    open_card = CompositeVideoClip([still, badge], size=(W, H))

    final = concatenate_videoclips([open_card] + clips, method="compose")
    out = OUT / "Street_Interview_AI_Campus.mp4"
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
    reporter.close()
    student.close()

    iphone = OUT / "Street_Interview_AI_Campus_iPhone.mp4"
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
    return iphone


if __name__ == "__main__":
    build()

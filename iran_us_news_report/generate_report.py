#!/usr/bin/env python3
"""
Professional news report video: Iran–US conflict situation update.
Includes TTS narration, broadcast-style graphics, and 3D situation maps.
Sources: AP, Al Jazeera, Reuters — as of 26–27 July 2026.
"""

from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from gtts import gTTS
from matplotlib import patheffects
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
AUDIO = ROOT / "audio"
FRAMES = ROOT / "frames"
OUTPUT = ROOT / "output"
for d in (ASSETS, AUDIO, FRAMES, OUTPUT):
    d.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
FPS = 30

# Broadcast palette
NAVY = (8, 18, 42)
DEEP = (12, 28, 58)
RED = (196, 30, 58)
GOLD = (212, 175, 55)
WHITE = (245, 247, 250)
MUTED = (160, 175, 195)
CYAN = (64, 196, 220)
TEAL = (20, 140, 150)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def gradient_bg(w: int = W, h: int = H) -> Image.Image:
    img = Image.new("RGB", (w, h), NAVY)
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(NAVY[0] * (1 - t) + DEEP[0] * t)
        g = int(NAVY[1] * (1 - t) + DEEP[1] * t + 8 * math.sin(t * math.pi))
        b = int(NAVY[2] * (1 - t) + DEEP[2] * t)
        for x in range(0, w, 4):
            # subtle vignette / light beams
            edge = abs(x - w / 2) / (w / 2)
            rr = max(0, min(255, int(r - edge * 12)))
            gg = max(0, min(255, int(g - edge * 8)))
            bb = max(0, min(255, int(b + (1 - edge) * 6)))
            for dx in range(4):
                if x + dx < w:
                    px[x + dx, y] = (rr, gg, bb)
    # soft diagonal light
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(12):
        alpha = 8
        od.polygon(
            [(w * 0.55 + i * 18, 0), (w * 0.72 + i * 18, 0), (w * 0.35 + i * 18, h), (w * 0.18 + i * 18, h)],
            fill=(CYAN[0], CYAN[1], CYAN[2], alpha),
        )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return img


def draw_breaking_bar(draw: ImageDraw.ImageDraw, y: int = 48) -> None:
    draw.rectangle([0, y, W, y + 56], fill=RED)
    draw.text((36, y + 10), "BREAKING NEWS", font=font(28, True), fill=WHITE)
    draw.rectangle([320, y + 12, 324, y + 44], fill=WHITE)
    draw.text((340, y + 12), "MIDDLE EAST  ·  SPECIAL REPORT", font=font(22, True), fill=WHITE)


def draw_ticker(draw: ImageDraw.ImageDraw, text: str, y: int = H - 64) -> None:
    draw.rectangle([0, y, W, H], fill=(4, 10, 28))
    draw.rectangle([0, y, W, y + 4], fill=GOLD)
    draw.text((28, y + 16), text, font=font(22), fill=WHITE)


def draw_lower_third(img: Image.Image, headline: str, sub: str) -> Image.Image:
    overlay = img.convert("RGBA")
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    top = H - 230
    d.rectangle([0, top, W, H - 64], fill=(8, 16, 36, 220))
    d.rectangle([0, top, 12, H - 64], fill=RED + (255,))
    d.rectangle([0, top, W, top + 4], fill=GOLD + (255,))
    d.text((40, top + 28), headline, font=font(42, True), fill=WHITE + (255,))
    d.text((40, top + 90), sub, font=font(26), fill=MUTED + (255,))
    return Image.alpha_composite(overlay, panel).convert("RGB")


def make_title_card() -> Path:
    img = gradient_bg()
    d = ImageDraw.Draw(img)
    draw_breaking_bar(d)
    # Network mark
    d.rounded_rectangle([40, 130, 220, 190], radius=8, fill=RED)
    d.text((58, 142), "WORLD DESK", font=font(24, True), fill=WHITE)
    d.text((40, 320), "IRAN–U.S. CONFLICT", font=font(78, True), fill=WHITE)
    d.text((40, 420), "STRIKES PAUSED  ·  DIPLOMACY RETURNS", font=font(36, True), fill=GOLD)
    d.text(
        (40, 500),
        "Situation briefing  ·  27 July 2026",
        font=font(28),
        fill=MUTED,
    )
    # Key flash points
    boxes = [
        (40, 620, "DAY 2", "Mutual pause"),
        (420, 620, "HORMUZ", "Shipping at 3-week low"),
        (900, 620, "OMAN", "Mediation talks"),
        (1380, 620, "BLOCKADE", "U.S. naval hold"),
    ]
    for x, y, title, body in boxes:
        d.rounded_rectangle([x, y, x + 340, y + 140], radius=10, fill=(18, 34, 68), outline=CYAN, width=2)
        d.text((x + 24, y + 28), title, font=font(26, True), fill=CYAN)
        d.text((x + 24, y + 74), body, font=font(22), fill=WHITE)
    draw_ticker(d, "LIVE  ·  U.S. and Iran hold fire for second day  ·  Ceasefire talks via Oman  ·  Strait of Hormuz remains contested")
    path = ASSETS / "title_card.png"
    img.save(path)
    return path


def make_segment_card(title: str, bullets: list[str], eyebrow: str) -> Path:
    img = gradient_bg()
    d = ImageDraw.Draw(img)
    draw_breaking_bar(d)
    d.text((40, 140), eyebrow.upper(), font=font(22, True), fill=CYAN)
    d.text((40, 190), title, font=font(54, True), fill=WHITE)
    d.rectangle([40, 270, 280, 276], fill=GOLD)
    y = 320
    for i, bullet in enumerate(bullets):
        d.ellipse([48, y + 14, 64, y + 30], fill=RED)
        # wrap text
        words = bullet.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font(28).getlength(test) < 1700:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for j, line in enumerate(lines):
            d.text((88, y + j * 40), line, font=font(28), fill=WHITE)
        y += 40 * len(lines) + 28
    draw_ticker(d, "WORLD DESK  ·  Analysis based on AP, Al Jazeera, Reuters reporting  ·  27 July 2026")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title.lower())[:40]
    path = ASSETS / f"segment_{safe}.png"
    img.save(path)
    return path


def make_map_still_overlay(
    frame_path: Path,
    headline: str,
    sub: str,
    banner: str = "3D SITUATION MAP  ·  PERSIAN GULF / STRAIT OF HORMUZ",
    out_name: str | None = None,
) -> Path:
    base = Image.open(frame_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    # darken edges for broadcast look
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, 0, W, 90], fill=(8, 16, 36, 200))
    d.text((36, 28), banner, font=font(24, True), fill=WHITE + (255,))
    composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    composed = draw_lower_third(composed, headline, sub)
    out = ASSETS / (out_name or (frame_path.stem + "_broadcast.png"))
    composed.save(out)
    return out


def render_3d_map_frames(n_frames: int = 90) -> list[Path]:
    """Render rotating 3D Gulf / Hormuz situation graphic frames."""
    out_dir = FRAMES / "map3d"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # Approximate geographic points (lon, lat) — stylized for clarity
    # Iran coast, UAE/Oman, Hormuz choke point
    iran_coast = np.array(
        [
            [48.5, 30.0],
            [50.0, 28.5],
            [52.0, 27.5],
            [54.0, 26.8],
            [56.0, 26.5],
            [57.0, 27.0],
            [58.5, 25.5],
            [60.0, 25.2],
        ]
    )
    arabia = np.array(
        [
            [48.0, 28.5],
            [50.0, 26.0],
            [52.5, 25.0],
            [54.5, 24.5],
            [56.2, 24.8],
            [57.5, 24.2],
            [59.0, 22.5],
        ]
    )
    hormuz = np.array([56.5, 26.5])
    tehran = np.array([51.4, 35.7])
    dubai = np.array([55.3, 25.2])
    muscat = np.array([58.5, 23.6])
    bahrain = np.array([50.6, 26.0])
    kuwait = np.array([47.9, 29.3])

    # Ship lane through Hormuz
    lane_t = np.linspace(0, 1, 40)
    lane = np.column_stack(
        [
            52 + 7 * lane_t + 0.4 * np.sin(lane_t * math.pi * 2),
            26.2 + 0.6 * np.sin(lane_t * math.pi) - 0.3 * lane_t,
        ]
    )

    for i in range(n_frames):
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        fig.patch.set_facecolor("#08122a")
        ax.set_facecolor("#0c1c3a")

        elev = 28 + 6 * math.sin(i / n_frames * 2 * math.pi)
        azim = -55 + i * (70 / n_frames)
        ax.view_init(elev=elev, azim=azim)

        # Ocean base plane
        gx = np.linspace(47, 61, 40)
        gy = np.linspace(22, 36, 40)
        GX, GY = np.meshgrid(gx, gy)
        GZ = np.zeros_like(GX) - 0.15
        # gentle wave
        GZ += 0.05 * np.sin(GX * 0.8 + i * 0.15) * np.cos(GY * 0.6)
        ax.plot_surface(GX, GY, GZ, color="#123a5c", alpha=0.55, linewidth=0, antialiased=True)

        # Terrain raised plates
        def plate(pts, height, color, alpha=0.92):
            xs, ys = pts[:, 0], pts[:, 1]
            # close polygon extrusion
            for z0, z1 in [(0, height)]:
                ax.plot(xs, ys, np.full_like(xs, z1), color=color, lw=2.5, alpha=alpha)
            # fill top via triangulation-ish scatter surface
            ax.plot_trisurf(xs, ys, np.full(len(xs), height), color=color, alpha=0.35, linewidth=0)

        plate(iran_coast, 1.8, "#8b3a3a")
        plate(arabia, 1.2, "#3d5a40")

        # Labels / markers
        markers = [
            (tehran[0], tehran[1], 2.4, "TEHRAN", "#ff6b6b"),
            (dubai[0], dubai[1], 1.6, "DUBAI", "#7ec8e3"),
            (muscat[0], muscat[1], 1.5, "MUSCAT", "#7ec8e3"),
            (bahrain[0], bahrain[1], 1.5, "BAHRAIN", "#f0c75e"),
            (kuwait[0], kuwait[1], 1.6, "KUWAIT", "#f0c75e"),
            (hormuz[0], hormuz[1], 2.0, "HORMUZ", "#ffd700"),
        ]
        for x, y, z, label, color in markers:
            ax.scatter([x], [y], [z], s=80, c=color, depthshade=True, edgecolors="white", linewidths=0.6)
            ax.text(x, y, z + 0.35, label, color="white", fontsize=9, fontweight="bold")

        # Animated shipping lane + vessels
        ax.plot(lane[:, 0], lane[:, 1], np.full(len(lane), 0.2), color="#40c4dc", lw=2.5, alpha=0.85)
        ship_idx = int((i / n_frames) * (len(lane) - 1))
        for offset in (0, 8, 16):
            si = (ship_idx + offset) % len(lane)
            ax.scatter(
                [lane[si, 0]],
                [lane[si, 1]],
                [0.45],
                s=55,
                c="#ffffff",
                marker="^",
                depthshade=False,
            )

        # U.S. naval blockade arc (Gulf of Oman side)
        block_t = np.linspace(0, math.pi * 0.55, 30)
        bx = 59.2 + 1.4 * np.cos(block_t)
        by = 24.8 + 1.1 * np.sin(block_t)
        bz = np.full_like(bx, 0.55)
        ax.plot(bx, by, bz, color="#4aa3ff", lw=3, linestyle="--", alpha=0.9)
        ax.text(60.2, 25.5, 1.0, "U.S. BLOCKADE", color="#4aa3ff", fontsize=8, fontweight="bold")

        # Pulse rings at Hormuz
        pulse = 0.3 + 0.7 * abs(math.sin(i / n_frames * 4 * math.pi))
        theta = np.linspace(0, 2 * math.pi, 60)
        rx = hormuz[0] + pulse * 1.2 * np.cos(theta)
        ry = hormuz[1] + pulse * 0.7 * np.sin(theta)
        ax.plot(rx, ry, np.full_like(rx, 0.3), color="#ffd700", lw=1.5, alpha=0.7)

        # Strike pause indicator beams (faded)
        ax.plot(
            [54.5, hormuz[0]],
            [28.5, hormuz[1]],
            [2.0, 0.5],
            color="#ff6b6b",
            lw=1.2,
            alpha=0.25 + 0.15 * math.sin(i * 0.2),
            linestyle=":",
        )

        ax.set_xlim(47, 61)
        ax.set_ylim(22, 36)
        ax.set_zlim(-0.5, 3.2)
        ax.set_axis_off()
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_edgecolor("#08122a")

        # Legend box via fig text
        fig.text(
            0.02,
            0.08,
            "FLASHPOINT: Strait of Hormuz  ·  ~20% of global oil & gas transit (pre-war)\n"
            "STATUS: Mutual strike pause (Day 2)  ·  Naval blockade remains in effect",
            color="#c8d4e6",
            fontsize=11,
            fontfamily="DejaVu Sans",
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#0a162e", edgecolor="#40c4dc", alpha=0.9),
        )

        path = out_dir / f"frame_{i:04d}.png"
        fig.savefig(path, dpi=100, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
        paths.append(path)
        if i % 15 == 0:
            print(f"  3D map frame {i+1}/{n_frames}")

    return paths


def render_timeline_3d(n_frames: int = 60) -> list[Path]:
    """3D timeline / escalation graphic."""
    out_dir = FRAMES / "timeline3d"
    out_dir.mkdir(parents=True, exist_ok=True)
    events = [
        ("Late Feb 2026", "War begins\nU.S.–Israel / Iran", 0),
        ("Mid-Jun 2026", "60-day interim\ndeal signed", 1),
        ("Early Jul", "Hormuz shipping\nattacks escalate", 2),
        ("~13 nights", "U.S. airstrikes on\nIranian targets", 3),
        ("24–26 Jul", "Mutual pause\n& Oman talks", 4),
    ]
    paths = []
    for i in range(n_frames):
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        fig.patch.set_facecolor("#08122a")
        ax.set_facecolor("#08122a")
        ax.view_init(elev=18, azim=-40 + i * 0.4)

        xs = np.arange(len(events))
        heights = [1.2, 1.6, 2.4, 3.0, 1.8]
        colors = ["#c41e3a", "#d4af37", "#c41e3a", "#c41e3a", "#40c4dc"]
        active = min(len(events) - 1, int(i / n_frames * (len(events) + 0.5)))

        for j, (label, desc, _) in enumerate(events):
            h = heights[j]
            alpha = 1.0 if j <= active else 0.25
            # bar as a rectangular prism approximation
            x0, y0 = j * 1.4, 0
            w, d = 0.7, 0.7
            # top
            ax.bar3d(x0, y0, 0, w, d, h, color=colors[j], alpha=alpha, shade=True)
            ax.text(x0 + 0.2, -0.6, 0.1, label, color="white", fontsize=8, rotation=0)
            if j <= active:
                ax.text(x0 - 0.1, 1.1, h + 0.2, desc, color="#e8eef8", fontsize=8)

        # connecting spine
        ax.plot(
            [j * 1.4 + 0.35 for j in range(len(events))],
            [0.35] * len(events),
            [0.05] * len(events),
            color="#40c4dc",
            lw=2,
            alpha=0.6,
        )

        ax.set_xlim(-0.5, 7)
        ax.set_ylim(-1.5, 2.5)
        ax.set_zlim(0, 4)
        ax.set_axis_off()
        fig.text(0.05, 0.9, "CONFLICT TIMELINE  ·  FIVE MONTHS OF WAR", color="white", fontsize=18, fontweight="bold")
        fig.text(0.05, 0.85, "From late February outbreak to the July 2026 strike pause", color="#9eb0c8", fontsize=12)

        path = out_dir / f"frame_{i:04d}.png"
        fig.savefig(path, dpi=100, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
        paths.append(path)
        if i % 15 == 0:
            print(f"  timeline frame {i+1}/{n_frames}")
    return paths


SEGMENTS = [
    {
        "id": "open",
        "title_card": True,
        "narration": (
            "This is a World Desk special report. As of July twenty-seventh, twenty twenty-six, "
            "the United States and Iran have paused military strikes for a second consecutive day, "
            "opening a fragile window for diplomacy after nearly two weeks of intensifying exchanges."
        ),
    },
    {
        "id": "map",
        "kind": "map3d",
        "headline": "Strait of Hormuz: The Strategic Flashpoint",
        "sub": "Shipping traffic at a three-week low  ·  U.S. naval blockade remains in effect",
        "narration": (
            "At the center of the crisis is the Strait of Hormuz, the narrow waterway between Iran and Oman "
            "that, before the war, carried roughly twenty percent of the world's oil and gas exports. "
            "Commercial shipping traffic is now at a three-week low. The U.S. military says its naval blockade "
            "of Iran remains in full effect, with commercial vessels redirected, disabled, or boarded. "
            "Iran continues to assert control over passage under a mid-June interim understanding."
        ),
    },
    {
        "id": "escalation",
        "eyebrow": "What happened",
        "title": "Two weeks of escalation",
        "bullets": [
            "U.S. conducted roughly 13 nights of airstrikes on Iranian coastal areas and infrastructure.",
            "Washington said strikes answered Iranian attacks on shipping in the Strait of Hormuz.",
            "Iran retaliated against regional sites hosting U.S. forces, including in Jordan, Bahrain, and Kuwait.",
            "Reports cited fatalities among service members at bases in Jordan and Iraq.",
        ],
        "narration": (
            "The latest surge followed Iranian fire at ships trying to transit Hormuz. "
            "For about thirteen nights, U.S. forces struck Iranian coastal targets and infrastructure. "
            "Iran answered with strikes on neighboring countries hosting American bases. "
            "Iranian and regional reporting described attacks affecting sites in Kuwait, Bahrain, and Jordan, "
            "with deaths reported among service members."
        ),
    },
    {
        "id": "timeline",
        "kind": "timeline3d",
        "headline": "Five Months of Conflict",
        "sub": "Late February war outbreak  →  June interim deal  →  July Hormuz escalation  →  Strike pause",
        "narration": (
            "The wider war dates to late February, when the United States and Israel began military operations against Iran. "
            "A sixty-day interim deal signed in mid-June briefly eased fighting, but major issues—especially Iran's nuclear program—"
            "were deferred. That arrangement frayed as disputes over Hormuz navigation returned to the center of the conflict."
        ),
    },
    {
        "id": "diplomacy",
        "eyebrow": "Diplomacy",
        "title": "Oman mediation & the pause",
        "bullets": [
            "U.S. Ambassador Mike Waltz: Trump is 'giving talks some space.'",
            "Omani officials held technical talks with Tehran on Hormuz navigation.",
            "Iran says it will halt strikes as long as the U.S. bombing pause holds.",
            "A regional mediator called the pause a 'positive signal' for de-escalation.",
        ],
        "narration": (
            "U.S. Ambassador to the United Nations Mike Waltz said President Trump is giving talks room to work, "
            "with Oman and other negotiators engaged at senior and technical levels. "
            "Iran's Foreign Ministry said talks with Oman on safe passage through Hormuz made progress. "
            "A senior Iranian official told Reuters Tehran will halt its own attacks as long as Washington does the same."
        ),
    },
    {
        "id": "outlook",
        "eyebrow": "What comes next",
        "title": "Fragile calm, unresolved stakes",
        "bullets": [
            "U.S. blockade continues; Iran and proxies keep regional pressure points active.",
            "Houthi threats around Bab al-Mandeb add risk to Red Sea energy routes.",
            "Netanyahu expected in Washington Tuesday to discuss Iran with Trump.",
            "Gasoline prices remain elevated as global energy markets watch Hormuz.",
        ],
        "narration": (
            "The calm remains fragile. The U.S. blockade continues, while Iranian-backed Houthi forces have raised pressure "
            "around the Bab al-Mandeb strait. Israeli Prime Minister Benjamin Netanyahu is expected to meet President Trump "
            "in Washington on Tuesday. Global energy markets remain on edge as gasoline prices have risen again. "
            "For World Desk, this has been a situation briefing on the Iran–U.S. conflict."
        ),
    },
]


def synthesize_narration(text: str, path: Path) -> Path:
    tts = gTTS(text=text, lang="en", tld="com")
    mp3 = path.with_suffix(".mp3")
    tts.save(str(mp3))
    # normalize / convert to wav for reliable duration
    wav = path.with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return wav


def frames_to_clip(
    frame_paths: list[Path],
    duration: float,
    headline: str,
    sub: str,
    banner: str = "3D SITUATION MAP  ·  PERSIAN GULF / STRAIT OF HORMUZ",
    overlay_prefix: str = "map",
):
    """Turn rendered frames into a looping/stretched video clip with lower-third."""
    n = len(frame_paths)
    clips = []
    frame_dur = duration / n
    overlay_dir = ASSETS / f"overlays_{overlay_prefix}"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    for i, fp in enumerate(frame_paths):
        broadcast = make_map_still_overlay(
            fp,
            headline,
            sub,
            banner=banner,
            out_name=f"overlays_{overlay_prefix}/{i:04d}.png",
        )
        clips.append(ImageClip(str(broadcast)).with_duration(frame_dur))
    return concatenate_videoclips(clips, method="compose")


def image_with_audio(image_path: Path, audio_path: Path, min_duration: float = 3.0):
    audio = AudioFileClip(str(audio_path))
    dur = max(min_duration, audio.duration + 0.4)
    clip = ImageClip(str(image_path)).with_duration(dur).with_audio(audio)
    return clip


def load_existing_frames(dir_path: Path) -> list[Path]:
    frames = sorted(dir_path.glob("frame_*.png"))
    return frames


def build_video(reuse_media: bool = True):
    print("=== Generating broadcast assets ===")
    title = make_title_card()

    print("=== Synthesizing narration ===")
    audio_paths = {}
    for seg in SEGMENTS:
        ap = AUDIO / f"{seg['id']}.wav"
        if reuse_media and ap.exists():
            print(f"  reuse TTS: {seg['id']}")
            audio_paths[seg["id"]] = ap
        else:
            print(f"  TTS: {seg['id']}")
            audio_paths[seg["id"]] = synthesize_narration(seg["narration"], ap)

    map_dir = FRAMES / "map3d"
    tl_dir = FRAMES / "timeline3d"
    if reuse_media and map_dir.exists() and list(map_dir.glob("frame_*.png")):
        print("=== Reusing 3D situation map frames ===")
        map_frames = load_existing_frames(map_dir)
    else:
        print("=== Rendering 3D situation map ===")
        map_frames = render_3d_map_frames(72)

    if reuse_media and tl_dir.exists() and list(tl_dir.glob("frame_*.png")):
        print("=== Reusing 3D timeline frames ===")
        timeline_frames = load_existing_frames(tl_dir)
    else:
        print("=== Rendering 3D timeline ===")
        timeline_frames = render_timeline_3d(48)

    print("=== Composing video ===")
    clips = []

    # Opening
    clips.append(image_with_audio(title, audio_paths["open"]))

    # 3D map segment
    map_audio = AudioFileClip(str(audio_paths["map"]))
    map_clip = frames_to_clip(
        map_frames,
        duration=max(map_audio.duration + 0.5, len(map_frames) / FPS),
        headline=SEGMENTS[1]["headline"],
        sub=SEGMENTS[1]["sub"],
        banner="3D SITUATION MAP  ·  PERSIAN GULF / STRAIT OF HORMUZ",
        overlay_prefix="map",
    ).with_audio(map_audio)
    clips.append(map_clip)

    # Escalation card
    esc = SEGMENTS[2]
    esc_img = make_segment_card(esc["title"], esc["bullets"], esc["eyebrow"])
    clips.append(image_with_audio(esc_img, audio_paths["escalation"]))

    # Timeline 3D
    tl_audio = AudioFileClip(str(audio_paths["timeline"]))
    tl_clip = frames_to_clip(
        timeline_frames,
        duration=max(tl_audio.duration + 0.5, len(timeline_frames) / FPS),
        headline=SEGMENTS[3]["headline"],
        sub=SEGMENTS[3]["sub"],
        banner="3D CONFLICT TIMELINE  ·  FEB–JUL 2026",
        overlay_prefix="timeline",
    ).with_audio(tl_audio)
    clips.append(tl_clip)

    # Diplomacy
    dip = SEGMENTS[4]
    dip_img = make_segment_card(dip["title"], dip["bullets"], dip["eyebrow"])
    clips.append(image_with_audio(dip_img, audio_paths["diplomacy"]))

    # Outlook
    out = SEGMENTS[5]
    out_img = make_segment_card(out["title"], out["bullets"], out["eyebrow"])
    clips.append(image_with_audio(out_img, audio_paths["outlook"]))

    final = concatenate_videoclips(clips, method="compose")
    out_path = OUTPUT / "Iran_US_War_News_Report_27Jul2026.mp4"
    print(f"=== Writing {out_path} ===")
    final.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="6000k",
        audio_bitrate="192k",
        threads=4,
        logger="bar",
    )
    final.close()
    print("DONE:", out_path)
    return out_path


if __name__ == "__main__":
    build_video()

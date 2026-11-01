from pathlib import Path
from PIL import Image
import subprocess
import imageio_ffmpeg

source_dir = Path("images")
dest_dir = Path("videos")
dest_dir.mkdir(exist_ok=True)
fps = 12
for source in sorted(source_dir.glob("*.webp")):
    with Image.open(source) as im:
        if getattr(im, "n_frames", 1) <= 1:
            print(f"Skipping still image: {source}")
            continue
        w, h = im.size
        w, h = w - w % 2, h - h % 2
        destination = dest_dir / f"{source.stem}.mp4"
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
            "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(destination)]
        print(f"Converting {source} ({im.n_frames} source frames)", flush=True)
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        sent = 0
        try:
            next_sample = 0.0
            elapsed = 0.0
            last_rgb = None
            for i in range(im.n_frames):
                im.seek(i)
                rgba = im.convert("RGBA")
                backdrop = Image.new("RGB", rgba.size, (16, 43, 57))
                backdrop.paste(rgba, mask=rgba.getchannel("A"))
                rgb = backdrop.crop((0, 0, w, h)).tobytes()
                last_rgb = rgb
                duration_ms = im.info.get("duration", 80) or 80
                elapsed += max(20, float(duration_ms)) / 1000.0
                while next_sample < elapsed:
                    process.stdin.write(rgb)
                    sent += 1
                    next_sample += 1 / fps
            if sent == 0 and last_rgb:
                process.stdin.write(last_rgb)
                sent += 1
        finally:
            process.stdin.close()
        result = process.wait()
        if result != 0:
            raise RuntimeError(f"ffmpeg failed for {source}, exit code {result}")
        if destination.stat().st_size > 100_000_000:
            raise RuntimeError(f"Video exceeds GitHub file limit: {destination}")
        print(f"Created {destination} ({sent} frames, {destination.stat().st_size} bytes)", flush=True)

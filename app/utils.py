import os
import subprocess

def merge_video_audio(video_path, audio_path, output_path):
    """
    Merge video and audio using ffmpeg. Returns True if successful, False otherwise.
    """
    try:
        # -y to overwrite, -shortest to cut audio/video to shortest length
        cmd = [
            'ffmpeg', '-i', video_path, '-i', audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-shortest', '-y', output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print(f"ffmpeg merge error: {e}")
        return False

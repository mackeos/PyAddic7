"""Find the best English subtitle for a video file and download it.

Direct port of the SearchBest example from matcornic/addic7ed.
"""

from pyaddic7 import Addic7edClient

client = Addic7edClient()

video_file = "South.Park.S25E04.720p.WEB.h264-BAE"
show_name, subtitle = client.search_best(video_file, "English")

print(show_name)          # e.g. South Park - 25x04 - Back to the Cold War
print(subtitle.version)   # e.g. WEB.BAE
print(subtitle.language)  # English

client.download_to_file(subtitle, video_file + ".srt")
print("Subtitle downloaded to", video_file + ".srt")

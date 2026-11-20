"""Search completed subtitles for South Park S25E04 and download the first one.

Direct port of example.mjs from same31/addic7ed-api.
"""

from pyaddic7 import download, get_show_titles, search

print("Searching all show titles...")
show_titles = get_show_titles()
print("All available show titles:", show_titles[:10], "... ({} total)".format(len(show_titles)))

print("Searching episode subtitles: South Park S25E04")
subtitles = search("South Park", season=25, episode=4)

if subtitles:
    sub = subtitles[0]
    print("Downloading first result:", sub)
    download(sub, "./South.Park.S25E04.srt")
    print("Subtitles file downloaded.")
else:
    print("No subtitle found.")

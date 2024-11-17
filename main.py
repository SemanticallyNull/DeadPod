import urllib.request
import tempfile
import io

from defusedxml.minidom import parse
from fastapi import FastAPI,Request,Response
from fastapi.responses import StreamingResponse,RedirectResponse
from pydub import AudioSegment,silence
from pydub.utils import mediainfo
import truststore

truststore.inject_into_ssl()
app = FastAPI(docs_url=None, redoc_url=None)

def remove_ads(url: str):
    with tempfile.NamedTemporaryFile() as podcast_file:
        urllib.request.urlretrieve(url, podcast_file.name)

        podcast_ep = AudioSegment.from_mp3(podcast_file.name)
        silences = silence.detect_silence(podcast_ep, min_silence_len=250,
                                          silence_thresh=-80, seek_step=25)

        composed = AudioSegment.empty()

        for idx, x in enumerate(silences):
            _, end = x
            if len(silences) > idx + 2:
                _, nextend = silences[idx + 1]
            else:
                nextend = podcast_ep.duration_seconds * 1000
            if nextend - end > 300000:
                composed = composed.append(podcast_ep[end:nextend], crossfade=0)

        buffer = io.BytesIO()
        composed.export(buffer, format="mp3",tags=mediainfo(podcast_file.name))
        return buffer

@app.head("/rss/{url:path}")
async def rss_head(url: str):
    return {}

@app.get("/rss/{url:path}")
async def rss(url: str, request: Request):
    with tempfile.NamedTemporaryFile() as feed_file:
        urllib.request.urlretrieve(url, feed_file.name)
        dom = parse(feed_file.name)
        for elem in dom.getElementsByTagName("title"):
            title = elem.firstChild.data
            elem.firstChild.data = f"[DEAD] {title}"
        for elem in dom.getElementsByTagName("itunes:title"):
            title = elem.firstChild.data
            elem.firstChild.data = f"[DEAD] {title}"
        for elem in dom.getElementsByTagName("enclosure"):
            url = elem.attributes["url"].value
            elem.attributes["url"].value = f"{request.base_url}deadpodcast/{url}"
        for elem in dom.getElementsByTagName("media:content"):
            if elem.attributes["type"].value == "audio/mpeg":
                url = elem.attributes["url"].value
                elem.attributes["url"].value = f"{request.base_url}deadpodcast/{url}"
        return Response(content=dom.toxml(), media_type="text/xml")

@app.get("/deadpodcast/{url:path}")
async def dead_podcast(url: str):
    return StreamingResponse(remove_ads(url), media_type="audio/mpeg")

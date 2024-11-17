import io
import logging
import sys
import tempfile
from urllib.error import URLError,HTTPError
import urllib.request
import urllib.error

from defusedxml.minidom import parse
from fastapi import FastAPI,Request,Response
from fastapi.responses import StreamingResponse
from pydub import AudioSegment,silence
from pydub.utils import mediainfo
import truststore

truststore.inject_into_ssl()
app = FastAPI(name='DeadPod', docs_url=None, redoc_url=None)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

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

@app.head(
    "/rss/{url:path}",
    status_code=204,
)
async def rss_head(url: str, response: Response):
    return replicate_headers(f"https://{url}", response)

def replicate_headers(url: str, response: Response):
    try:
        upstream_resp = urllib.request.urlopen(url)
    except HTTPError as e:
        logger.info(f"replicate_headers: error retrieving headers from {url}: {e}")
        if 400 <= e.code < 500:
            return Response(status_code=e.code)
        else:
            return Response(status_code=502)
    except URLError as e:
        logger.info(f"replicate_headers: error parsing url \"{url}\": {e}")
        return Response(status_code=400)
    except Exception as e:
        logger.info(f"replicate_headers: unexpected error: {e}")
        return Response(status_code=500)

    for header in upstream_resp.headers:
        if header not in ["Content-Length", "Content-Type", "ETag"]:
            response.headers[header] = upstream_resp.headers[header]

@app.get("/rss/{url:path}")
async def rss(url: str, request: Request):
    with tempfile.NamedTemporaryFile() as feed_file:
        try:
            urllib.request.urlretrieve(f"https://{url}", feed_file.name)
        except HTTPError as e:
            logger.info(f"rss: error retrieving headers from {url}: {e}")
            if 400 <= e.code < 500:
                return Response(status_code=e.code)
            else:
                return Response(status_code=502)
        except URLError as e:
            logger.info(f"rss: error parsing url \"{url}\": {e}")
            return Response(status_code=400)
        except Exception as e:
            logger.info(f"rss: unexpected error: {e}")
            return Response(status_code=500)

        dom = parse(feed_file.name)
        for elem in dom.getElementsByTagName("title"):
            title = elem.firstChild.data
            elem.firstChild.data = f"[DEAD] {title}"
        for elem in dom.getElementsByTagName("itunes:title"):
            title = elem.firstChild.data
            elem.firstChild.data = f"[DEAD] {title}"
        for elem in dom.getElementsByTagName("enclosure"):
            enclosure_url = elem.attributes["url"].value.replace("https://", "")
            elem.attributes["url"].value = f"{request.base_url}deadpodcast/{enclosure_url}"
        for elem in dom.getElementsByTagName("media:content"):
            if elem.attributes["type"].value == "audio/mpeg":
                media_url = elem.attributes["url"].value.replace("https://", "")
                elem.attributes["url"].value = f"{request.base_url}deadpodcast/{media_url}"
        return Response(content=dom.toxml(), media_type="text/xml")

@app.head(
    "/deadpodcast/{url:path}",
    status_code=204,
)
async def deadpodcast_head(url: str, response: Response):
    return replicate_headers(f"https://{url}", response)

@app.get("/deadpodcast/{url:path}")
async def dead_podcast(url: str):
    try:
        dead = remove_ads(f"https://{url}")
    except HTTPError as e:
        logger.info(f"rss: error retrieving headers from {url}: {e}")
        if 400 <= e.code < 500:
            return Response(status_code=e.code)
        else:
            return Response(status_code=502)
    except URLError as e:
        logger.info(f"rss: error parsing url \"{url}\": {e}")
        return Response(status_code=400)
    except Exception as e:
        logger.info(f"rss: unexpected error: {e}")
        return Response(status_code=500)

    return StreamingResponse(dead, media_type="audio/mpeg")
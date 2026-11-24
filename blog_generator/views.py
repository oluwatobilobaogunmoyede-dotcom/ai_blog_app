from django.views.decorators.csrf import ensure_csrf_cookie
import re
from urllib.parse import urlparse, parse_qs

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI


def get_youtube_video_id(url):
    """Extract the YouTube video ID from a YouTube URL."""

    parsed_url = urlparse(url)

    if parsed_url.hostname in ["youtu.be", "www.youtu.be"]:
        video_id = parsed_url.path.strip("/")

    elif parsed_url.hostname in [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com"
    ]:
        if parsed_url.path == "/watch":
            video_id = parse_qs(parsed_url.query).get("v", [""])[0]

        elif parsed_url.path.startswith(("/embed/", "/shorts/")):
            video_id = parsed_url.path.split("/")[2]

        else:
            return None

    else:
        return None

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None

    return video_id


@ensure_csrf_cookie
def index(request):
    return render(request, "index.html")

@require_POST
def generate_blog(request):
    youtube_link = request.POST.get("youtube_link", "").strip()

    if not youtube_link:
        return JsonResponse({
            "error": "Please enter a YouTube video link."
        }, status=400)

    video_id = get_youtube_video_id(youtube_link)

    if not video_id:
        return JsonResponse({
            "error": "Please enter a valid YouTube video link."
        }, status=400)

    try:
        # Get the YouTube transcript
        transcript = YouTubeTranscriptApi().fetch(video_id)

        transcript_text = " ".join(
            snippet.text for snippet in transcript
        )

        if not transcript_text.strip():
            return JsonResponse({
                "error": "No transcript was found for this video."
            }, status=400)

        # Limit transcript length
        transcript_text = transcript_text[:30000]

        # Connect to OpenAI
        client = OpenAI()

        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions=(
                "You are a professional blog writer. "
                "Create a clear, engaging, well-structured blog article "
                "based on the supplied YouTube transcript. "
                "Include a suitable title, introduction, headings, "
                "and conclusion. Do not invent facts."
            ),
            input=transcript_text
        )

        blog_content = response.output_text

        return JsonResponse({
            "blog": blog_content
        })

    except Exception as error:
        print("Blog generation error:", str(error))

        return JsonResponse({
            "error": (
                "We could not generate the blog. "
                "Check that the video has available captions "
                "and your OpenAI API account is active."
            )
        }, status=500)

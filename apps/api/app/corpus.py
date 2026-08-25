from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

TIMESTAMP_PATTERN = r"\d{1,2}:\d{2}(?::\d{2})?"
NAMED_HEADER = re.compile(
    rf"^(?P<speaker>.+?)\s+\((?P<timestamp>{TIMESTAMP_PATTERN})\):\s*$"
)
ANONYMOUS_HEADER = re.compile(rf"^\((?P<timestamp>{TIMESTAMP_PATTERN})\):\s*$")
TOPIC_LINK = re.compile(r"\.\./episodes/(?P<slug>[^/]+)/transcript\.md")
TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.-]+", re.IGNORECASE)
EVIDENCE_BUILD_VERSION = "conversation-v2"
TARGET_EVIDENCE_WORDS = 260
MAX_EVIDENCE_WORDS = 340

INTRO_MARKERS = ("today my guest is", "today's guest is", "today’s guest is", "my guest today is")
AD_MARKERS = (
    "this episode is brought to you by",
    "today's episode is brought to you by",
    "today’s episode is brought to you by",
    "this episode is sponsored by",
)
WELCOME_MARKERS = (
    "welcome to the podcast",
    "welcome to lenny's podcast",
    "welcome to lenny’s podcast",
)
RESUME_MARKERS = (
    "i'm going to come back to",
    "i am going to come back to",
    "let's get back to",
    "let us get back to",
    "back to our conversation",
    "back to the conversation",
)
RAPID_MARKERS = ("lightning round. are you ready", "rapid-fire round", "rapid fire round")
OUTRO_MARKERS = (
    "bye, everyone. thank you so much for listening",
    "thank you so much for listening. if you found this valuable",
    "see you in the next episode",
)


@dataclass(frozen=True)
class Turn:
    speaker: str
    timestamp: str
    seconds: int
    text: str
    named: bool
    region: str = "unknown"


@dataclass(frozen=True)
class Episode:
    id: str
    guest: str
    title: str
    youtube_url: str
    duration_seconds: int
    source_path: str
    content_hash: str
    metadata: dict[str, Any]
    turns: list[Turn]


@dataclass(frozen=True)
class EvidenceUnit:
    id: str
    episode_id: str
    guest: str
    title: str
    speaker: str
    question: str
    start_seconds: int
    end_seconds: int
    timestamp_label: str
    youtube_url: str
    excerpt: str
    search_document: str
    topics: list[str]


def timestamp_seconds(label: str) -> int:
    parts = [int(part) for part in label.split(":")]
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def format_timestamp(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in markers)


def _parse_markdown_turns(lines: list[str], start: int) -> list[Turn]:
    turns: list[Turn] = []
    speaker: str | None = None
    timestamp: str | None = None
    named = False
    body: list[str] = []

    def commit() -> None:
        nonlocal timestamp, body, named
        if speaker is None or timestamp is None:
            return
        text = "\n".join(body).strip()
        if text:
            turns.append(
                Turn(
                    speaker=speaker,
                    timestamp=timestamp,
                    seconds=timestamp_seconds(timestamp),
                    text=text,
                    named=named,
                )
            )
        timestamp = None
        body = []
        named = False

    for line in lines[start:]:
        named_match = NAMED_HEADER.match(line)
        anonymous_match = ANONYMOUS_HEADER.match(line)
        if named_match:
            commit()
            speaker = named_match.group("speaker").strip()
            timestamp = named_match.group("timestamp")
            named = True
        elif anonymous_match:
            commit()
            if speaker is None:
                continue
            timestamp = anonymous_match.group("timestamp")
            named = False
        elif timestamp is not None:
            body.append(line)
    commit()
    return turns


def _find_transition(text: str) -> tuple[int, str] | None:
    lowered = text.casefold()
    matches: list[tuple[int, str]] = []
    for marker in (*WELCOME_MARKERS, *RESUME_MARKERS):
        index = lowered.find(marker)
        if index > 0:
            if marker in WELCOME_MARKERS:
                sentence_start = max(text.rfind(". ", 0, index), text.rfind("! ", 0, index))
                index = sentence_start + 2 if sentence_start >= 0 else index
                matches.append((index, "welcome"))
            else:
                matches.append((index, "resume"))
    return min(matches, default=None, key=lambda item: item[0])


def _split_mixed_sponsor_turns(turns: list[Turn]) -> list[Turn]:
    expanded: list[Turn] = []
    sponsor_active = False
    for turn in turns:
        if _contains(turn.text, AD_MARKERS):
            sponsor_active = True
        transition = _find_transition(turn.text) if sponsor_active else None
        if transition is None:
            expanded.append(turn)
            continue
        index, kind = transition
        sponsor_text = turn.text[:index].strip()
        conversation_text = turn.text[index:].strip()
        if not sponsor_text or not conversation_text:
            expanded.append(turn)
            continue
        expanded.append(replace(turn, text=sponsor_text))
        synthetic_marker = (
            "welcome to the podcast" if kind == "welcome" else "i'm going to come back to"
        )
        expanded.append(replace(turn, text=f"{synthetic_marker}\n{conversation_text}"))
        sponsor_active = False
    return expanded


def _classify(turns: list[Turn], guest: str) -> list[Turn]:
    result: list[Turn] = []
    state = "cold_open"
    ad_speaker: str | None = None
    pending_interview = False
    guest_tokens = {token.casefold() for token in guest.split() if len(token) > 2}

    for turn in turns:
        text = turn.text
        speaker_tokens = {token.casefold() for token in turn.speaker.split()}
        is_guest = bool(guest_tokens & speaker_tokens) and "lenny" not in speaker_tokens

        if _contains(text, OUTRO_MARKERS):
            state = "outro"
            region = "outro"
        elif state == "outro":
            region = "outro"
        elif _contains(text, RAPID_MARKERS):
            state = "rapid_fire"
            region = "rapid_fire"
        elif state == "rapid_fire":
            region = "rapid_fire"
        elif pending_interview:
            state = "interview"
            pending_interview = False
            region = "interview"
        elif _contains(text, AD_MARKERS):
            state = "advertisement"
            ad_speaker = turn.speaker
            region = "advertisement"
        elif state == "advertisement" and _contains(text, WELCOME_MARKERS):
            state = "host_intro"
            pending_interview = True
            region = "host_intro"
        elif state == "advertisement" and _contains(text, RESUME_MARKERS):
            state = "interview"
            region = "interview"
        elif state == "advertisement" and turn.named and (is_guest or turn.speaker != ad_speaker):
            state = "interview"
            region = "interview"
        elif state == "advertisement":
            region = "advertisement"
        elif _contains(text, INTRO_MARKERS):
            state = "host_intro"
            region = "host_intro"
        elif state == "host_intro" and is_guest:
            state = "interview"
            region = "interview"
        elif state == "host_intro":
            region = "host_intro"
        elif state == "interview":
            region = "interview"
        else:
            region = "cold_open"
        result.append(replace(turn, region=region))

    if not any(turn.region == "interview" for turn in result):
        return [replace(turn, region="interview") for turn in result]
    return result


def parse_episode(path: Path) -> Episode:
    raw = path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"Missing frontmatter in {path}")
    closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    metadata = yaml.safe_load("\n".join(lines[1:closing])) or {}
    transcript_start = next(
        index + 1
        for index, line in enumerate(lines[closing + 1 :], start=closing + 1)
        if line.strip().casefold() == "## transcript"
    )
    guest = str(metadata.get("guest") or path.parent.name.replace("-", " ").title())
    turns = _classify(
        _split_mixed_sponsor_turns(_parse_markdown_turns(lines, transcript_start)), guest
    )
    duration = int(float(metadata.get("duration_seconds") or 0))
    return Episode(
        id=path.parent.name,
        guest=guest,
        title=str(metadata.get("title") or guest),
        youtube_url=str(metadata.get("youtube_url") or ""),
        duration_seconds=duration,
        source_path=path.as_posix(),
        content_hash=hashlib.sha256(raw).hexdigest(),
        metadata=metadata,
        turns=turns,
    )


def load_topic_map(index_dir: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    if not index_dir.exists():
        return mapping
    for path in sorted(index_dir.glob("*.md")):
        if path.name in {"README.md", "episodes.md"}:
            continue
        topic = path.stem.replace("-", " ")
        for match in TOPIC_LINK.finditer(path.read_text(encoding="utf-8")):
            mapping.setdefault(match.group("slug"), []).append(topic)
    return mapping


def _render_turn(turn: Turn) -> str:
    text = turn.text
    for marker in ("welcome to the podcast\n", "i'm going to come back to\n"):
        if text.casefold().startswith(marker):
            text = text[len(marker) :]
    return f"{turn.speaker} [{turn.timestamp}]: {text}"


def build_evidence_units(episode: Episode, topics: list[str]) -> list[EvidenceUnit]:
    eligible = [turn for turn in episode.turns if turn.region in {"interview", "rapid_fire"}]
    units: list[EvidenceUnit] = []
    current: list[Turn] = []
    question = ""
    guest_word_count = 0

    def flush() -> None:
        nonlocal current, question, guest_word_count
        if not current:
            return
        excerpt = "\n\n".join(_render_turn(turn) for turn in current)
        if len(TOKEN.findall(excerpt)) < 18:
            current = []
            question = ""
            guest_word_count = 0
            return
        start = current[0].seconds
        end = current[-1].seconds
        digest = hashlib.sha1(
            f"{episode.id}:{start}:{end}:{excerpt}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        unit_id = f"{episode.id}:{start}:{digest}"
        topic_text = ", ".join(topics)
        search_document = (
            f"Episode: {episode.title}\nGuest: {episode.guest}\nTopics: {topic_text}\n"
            f"Question: {question}\nEvidence:\n{excerpt}"
        )
        youtube = episode.youtube_url
        if youtube:
            separator = "&" if "?" in youtube else "?"
            youtube = f"{youtube}{separator}t={start}s"
        units.append(
            EvidenceUnit(
                id=unit_id,
                episode_id=episode.id,
                guest=episode.guest,
                title=episode.title,
                speaker=episode.guest,
                question=question,
                start_seconds=start,
                end_seconds=end,
                timestamp_label=f"{format_timestamp(start)}-{format_timestamp(end)}",
                youtube_url=youtube,
                excerpt=excerpt,
                search_document=search_document,
                topics=topics,
            )
        )
        current = []
        question = ""
        guest_word_count = 0

    for turn in eligible:
        is_host = "lenny" in turn.speaker.casefold()
        words = len(TOKEN.findall(turn.text))
        current_words = sum(len(TOKEN.findall(item.text)) for item in current)
        begins_question = is_host and "?" in turn.text and guest_word_count >= 45
        if begins_question:
            flush()
            current_words = 0
        elif current and current_words + words > MAX_EVIDENCE_WORDS and guest_word_count >= 45:
            flush()
        if not current and is_host:
            question = turn.text
        current.append(turn)
        if not is_host:
            guest_word_count += words
        if (
            sum(len(TOKEN.findall(item.text)) for item in current) >= TARGET_EVIDENCE_WORDS
            and guest_word_count >= 45
        ):
            flush()
    flush()
    return units

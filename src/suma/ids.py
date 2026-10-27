import re

_LABEL = re.compile(
    r"^(I|I-II|II-II|III) q\. (\d+) "
    r"(?:(pr)\.|a\. (\d+) (?:arg\. (\d+)|(s\. c\.)(?: (\d+))?|(co\.)|ad (\d+|arg\.)))$"
)
_RANGE = re.compile(r"^(I|I-II|II-II|III)\.q(\d+)(?:-(\d+))?$")


def label_to_id(label: str) -> str:
    m = _LABEL.match(label.strip())
    if not m:
        raise ValueError(f"Unrecognised Corpus Thomisticum label: {label!r}")
    part, q, pr, art, obj, sc, sc_n, co, ad = m.groups()
    base = f"{part}.q{int(q)}"
    if pr:
        return f"{base}.pr"
    base = f"{base}.a{int(art)}"
    if obj:
        return f"{base}.obj{int(obj)}"
    if sc:
        return f"{base}.sc{int(sc_n)}" if sc_n else f"{base}.sc"
    if co:
        return f"{base}.resp"
    return f"{base}.adarg" if ad == "arg." else f"{base}.ad{int(ad)}"


def article_of(unit_id: str) -> str:
    return ".".join(unit_id.split(".")[:3])


def parse_range(spec: str) -> tuple[str, int, int]:
    m = _RANGE.match(spec)
    if not m:
        raise ValueError(f"Bad range {spec!r}, expected e.g. I.q1-13")
    part, start, end = m.groups()
    return part, int(start), int(end or start)


def custom_id(article_id: str) -> str:
    return article_id.replace(".", "-")

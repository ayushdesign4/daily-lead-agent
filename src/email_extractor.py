"""Email extraction, cleaning, normalization, and strict validation."""

import re
import logging
from typing import List, Set, Any, Dict, Optional

logger = logging.getLogger(__name__)

# RFC-compliant base email regex
EMAIL_REGEX = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

# Unambiguous spaced email candidate regex (e.g. "creator @ gmail.com" or "creator @ gmail . com")
SPACED_EMAIL_REGEX = re.compile(
    r"\b([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9-]+(?:\.[a-zA-Z0-9-]+)*\s*\.\s*(?!\s+[A-Z])[A-Za-z]{2,10})\b"
)

# Common invalid file extensions that can masquerade as TLDs in text
INVALID_TLDS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "tiff",
    "mp4", "mp3", "mov", "avi", "mkv", "flv", "webm", "wav",
    "pdf", "zip", "tar", "gz", "rar", "7z", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "exe", "dmg", "iso", "apk", "bin", "js", "css", "html",
    "htm", "json", "xml", "py", "sh", "bat"
}

# Example / placeholder / non-routable domains to reject
EXCLUDED_DOMAINS = {
    "example.com", "example.org", "example.net", "sample.com", "domain.com",
    "email.com", "localhost", "sentry.io", "wixpress.com"
}

# Well-known free consumer webmail domains whose domain is strictly fixed
FREE_WEBMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "protonmail.com", "rediffmail.com", "aol.com", "zoho.com", "mail.com",
    "gmx.com", "yandex.com", "live.com", "msn.com"
}

# Common generic top-level domains (gTLDs) and recognized generic extensions
COMMON_GTLDS = {
    "com", "org", "net", "edu", "gov", "mil", "int", "info", "biz",
    "io", "ai", "co", "me", "tv", "cc", "app", "dev", "site", "online",
    "tech", "store", "xyz", "club", "live", "space", "pro", "agency",
    "global", "media", "digital", "studio", "life", "cloud", "world",
    "link", "press", "news", "design", "video", "expert", "guru", "today",
    "band", "art", "work", "fit", "law", "solutions", "services", "management",
    "consulting", "enterprises", "international", "company", "foundation",
    "community", "network", "systems", "technology", "academy", "center",
    "direct", "group", "guide", "house", "market", "photo", "plus", "school",
    "team", "zone", "name", "mobi", "travel", "museum", "jobs", "cat", "tel"
}

# Standard 2-letter Country-Code TLDs (ISO 3166-1 alpha-2)
CCTLDS = {
    "ac", "ad", "ae", "af", "ag", "ai", "al", "am", "ao", "aq", "ar", "as", "at",
    "au", "aw", "ax", "az", "ba", "bb", "bd", "be", "bf", "bg", "bh", "bi", "bj",
    "bm", "bn", "bo", "br", "bs", "bt", "bw", "by", "bz", "ca", "cc", "cd", "cf",
    "cg", "ch", "ci", "ck", "cl", "cm", "cn", "co", "cr", "cu", "cv", "cw", "cx",
    "cy", "cz", "de", "dj", "dk", "dm", "do", "dz", "ec", "ee", "eg", "eh", "er",
    "es", "et", "eu", "fi", "fj", "fk", "fm", "fo", "fr", "ga", "gb", "gd", "ge",
    "gf", "gg", "gh", "gi", "gl", "gm", "gn", "gp", "gq", "gr", "gs", "gt", "gu",
    "gw", "gy", "hk", "hm", "hn", "hr", "ht", "hu", "id", "ie", "il", "im", "in",
    "io", "iq", "ir", "is", "it", "je", "jm", "jo", "jp", "ke", "kg", "kh", "ki",
    "km", "kn", "kp", "kr", "kw", "ky", "kz", "la", "lb", "lc", "li", "lk", "lr",
    "ls", "lt", "lu", "lv", "ly", "ma", "mc", "md", "me", "mf", "mg", "mh", "mk",
    "ml", "mm", "mn", "mo", "mp", "mq", "mr", "ms", "mt", "mu", "mv", "mw", "mx",
    "my", "mz", "na", "nc", "ne", "nf", "ng", "ni", "nl", "no", "np", "nr", "nu",
    "nz", "om", "pa", "pe", "pf", "pg", "ph", "pk", "pl", "pm", "pn", "pr", "ps",
    "pt", "pw", "py", "qa", "re", "ro", "rs", "ru", "rw", "sa", "sb", "sc", "sd",
    "se", "sg", "sh", "si", "sk", "sl", "sm", "sn", "so", "sr", "ss", "st", "su",
    "sv", "sx", "sy", "sz", "tc", "td", "tf", "tg", "th", "tj", "tk", "tl", "tm",
    "tn", "to", "tr", "tt", "tv", "tw", "tz", "ua", "ug", "uk", "us", "uy", "uz",
    "va", "vc", "ve", "vg", "vi", "vn", "vu", "wf", "ws", "ye", "yt", "za", "zm", "zw"
}

VALID_TLDS = COMMON_GTLDS | CCTLDS

# Recognized multi-part country code second-level domains
MULTI_PART_CCTLDS = {
    "co.in", "com.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in",
    "ac.in", "edu.in", "gov.in", "mil.in", "res.in",
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "ltd.uk", "plc.uk", "net.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.nz", "net.nz", "org.nz", "govt.nz", "ac.nz",
    "com.br", "net.br", "org.br", "gov.br",
    "co.za", "org.za", "gov.za", "ac.za",
    "com.pk", "org.pk", "edu.pk", "gov.pk",
    "com.bd", "edu.bd", "gov.bd",
    "com.sg", "edu.sg", "gov.sg",
    "com.my", "edu.my", "gov.my",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
    "com.tr", "edu.tr", "gov.tr",
    "com.mx", "gob.mx", "edu.mx",
    "gob.ar", "com.ar", "cancilleria.gob.ar",
}

# Common English words and UI keywords that frequently get glued to TLDs in SERP snippets
GLUED_SNIPPET_WORDS = (
    "read", "more", "view", "links", "contact", "about", "website",
    "phone", "channel", "video", "india", "subscribe", "help", "share",
    "following", "followers", "official", "direct", "follow", "join",
    "posts", "post", "photos", "photo", "hours", "policies", "what",
    "here", "free", "shop", "support", "sales", "team", "inquiries"
)


def repair_domain_boundaries(domain: str) -> str:
    """
    Apply conservative domain boundary detection to safely remove extra snippet
    text, attached words, or trailing periods while preserving legitimate domains.
    """
    if not domain or not isinstance(domain, str):
        return ""

    dom = domain.strip().lower().rstrip(".-_")

    # 1. Immediate resolution for known free consumer providers
    for free_prov in FREE_WEBMAIL_DOMAINS:
        if dom == free_prov:
            return free_prov
        # E.g. "gmail.com.more", "gmail.com.read", "gmail.com.https", "gmail.com.this"
        if dom.startswith(free_prov + "."):
            return free_prov
        # Glued without dot: "gmail.comread", "gmail.commore"
        for word in GLUED_SNIPPET_WORDS:
            if dom == free_prov + word:
                return free_prov

    # 2. Check words glued directly to standard TLDs without a dot (e.g. "company.comread", "bestdiet.inread")
    for base_tld in ("com", "in", "org", "net", "co", "io", "edu", "gov", "site", "app", "dev", "tech"):
        for word in GLUED_SNIPPET_WORDS:
            glued_suffix = f".{base_tld}{word}"
            if dom.endswith(glued_suffix):
                dom = dom[:-len(word)]
                break

    # 3. Check multi-part ccTLDs with trailing attached words (e.g. "thebronzer.com.au.physical", "indiapost.gov.in.working")
    labels = dom.split(".")
    if len(labels) >= 4:
        two_part = f"{labels[-3]}.{labels[-2]}"
        if two_part in MULTI_PART_CCTLDS and labels[-1] not in VALID_TLDS:
            dom = ".".join(labels[:-1])
            labels = dom.split(".")

    # 4. Check standard single TLDs with trailing attached words (e.g. "bossdesign.com.policies", "quantaservices.com.what")
    labels = dom.split(".")
    if len(labels) >= 3:
        second_to_last = labels[-2]
        last = labels[-1]
        # If second-to-last is a recognized terminal TLD and last is not a valid TLD or matches a snippet word
        if second_to_last in COMMON_GTLDS and (last not in VALID_TLDS or last in GLUED_SNIPPET_WORDS):
            dom = ".".join(labels[:-1])

    return dom


def clean_and_normalize_email(raw_candidate: str) -> str:
    """
    Clean and normalize an email candidate:
    - strip surrounding whitespace and enclosing punctuation
    - handle 'mailto:' prefix
    - strip leading punctuation/hyphens from local part
    - apply conservative domain boundary repair
    - safely repair unambiguous spacing around @ and domain dots
    """
    if not raw_candidate or not isinstance(raw_candidate, str):
        return ""

    text = raw_candidate.strip().lower()
    # Strip common enclosing punctuation
    text = text.strip("<>\"'()[]{}.,:;!*?")

    # Handle mailto: prefix
    if text.startswith("mailto:"):
        text = text[7:].strip()

    # Safely repair unambiguous spacing around @ and dots if local and domain labels have no internal spaces
    if "@" in text and text.count("@") == 1:
        parts = text.split("@")
        local = parts[0].strip()
        domain = parts[1].strip()

        # Clean local part: remove leading unwanted punctuation attached from bullets or dashes
        local = local.lstrip(".-_+")
        if local.startswith("www."):
            local = local[4:].lstrip(".-_+")

        if " " not in local:
            domain_labels = [lbl.strip() for lbl in domain.split(".")]
            if all(" " not in lbl and len(lbl) > 0 for lbl in domain_labels) and len(domain_labels) >= 2:
                domain = ".".join(domain_labels)

        # Repair domain boundaries
        domain = repair_domain_boundaries(domain)
        text = f"{local}@{domain}"

    return text


def is_valid_email(email: str) -> bool:
    """
    Validate that an email strictly complies with standards:
    - RFC structure
    - Single @ with non-empty local and domain
    - Valid character constraints
    - Domain has at least two labels
    - TLD is recognized and not in invalid media extensions or excluded domains
    """
    if not email or len(email) > 254:
        return False

    if not EMAIL_REGEX.fullmatch(email):
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    local_part, domain = parts
    if not local_part or not domain:
        return False

    # Check local part constraints
    if len(local_part) > 64 or ".." in local_part or local_part.startswith(".") or local_part.endswith("."):
        return False

    # Check domain constraints
    if len(domain) > 253 or ".." in domain or domain.startswith(".") or domain.endswith("."):
        return False

    domain_parts = domain.split(".")
    if len(domain_parts) < 2:
        return False

    tld = domain_parts[-1].lower()
    if tld in INVALID_TLDS:
        return False

    if tld not in VALID_TLDS:
        return False

    if domain in EXCLUDED_DOMAINS:
        return False

    # Ensure every domain label contains only letters, digits, or hyphens (no leading/trailing hyphen)
    for label in domain_parts:
        if not label or len(label) > 63:
            return False
        if not re.match(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$", label):
            return False

    return True


def pre_sanitize_snippet_text(text: str) -> str:
    """
    Pre-process snippet text before regex searching to insert natural boundaries
    where Bright Data tag concatenation stripped whitespace between sentences or UI elements.
    """
    if not text or not isinstance(text, str):
        return ""

    s = text

    # 1. Period followed directly by a Capitalized word without whitespace:
    # e.g. "creator@gmail.com.Need more info" -> "creator@gmail.com. Need more info"
    s = re.sub(r"\.([A-Z][a-z]{2,})\b", r". \1", s)

    # 2. Known snippet glued keywords attached directly to common TLDs:
    # e.g. ".comread" -> ".com read", ".inread" -> ".in read"
    s = re.sub(
        r"\.(com|org|net|in|co|gov|edu|io|ai|app|dev|site|tech|tv|me)(?=(read|more|view|links|contact|about|website|phone|channel|video|india|subscribe))\b",
        r".\1 \2",
        s,
        flags=re.IGNORECASE,
    )

    # 3. Handle 'mailto:' without spaces
    s = re.sub(r"\bmailto:([A-Za-z0-9])", r"mailto: \1", s, flags=re.IGNORECASE)

    return s


def extract_emails_from_text(text: str) -> Set[str]:
    """
    Search arbitrary text for all genuine email addresses, handling snippet concatenation
    and domain boundary artifacts safely.
    """
    if not text or not isinstance(text, str):
        return set()

    valid_emails: Set[str] = set()

    # Pre-sanitize text to separate glued sentences/UI words
    sanitized_text = pre_sanitize_snippet_text(text)

    # Search in both sanitized text and original text
    texts_to_scan = [sanitized_text]
    if sanitized_text != text:
        texts_to_scan.append(text)

    for scan_text in texts_to_scan:
        # Pass 1: Standard RFC matches
        for item in EMAIL_REGEX.findall(scan_text):
            cleaned = clean_and_normalize_email(item)
            if is_valid_email(cleaned):
                valid_emails.add(cleaned)

        # Pass 2: Unambiguous spaced emails
        for match in SPACED_EMAIL_REGEX.finditer(scan_text):
            cleaned = clean_and_normalize_email(match.group(0))
            if is_valid_email(cleaned):
                valid_emails.add(cleaned)

    return valid_emails


def extract_emails_from_item(item: Dict[str, Any]) -> Set[str]:
    """
    Extract valid emails from any text fields of a scraper item,
    including organic results, title, description, url, snippets.
    """
    emails: Set[str] = set()

    def walk_and_extract(obj: Any):
        if isinstance(obj, str):
            emails.update(extract_emails_from_text(obj))
        elif isinstance(obj, dict):
            for val in obj.values():
                walk_and_extract(val)
        elif isinstance(obj, list):
            for elem in obj:
                walk_and_extract(elem)

    walk_and_extract(item)
    return emails


# Retain alias for Apify backward compatibility
extract_emails_from_apify_item = extract_emails_from_item


def extract_emails_from_dataset(dataset_items: List[Dict[str, Any]]) -> List[str]:
    """
    Extract all unique normalized valid emails from an entire scraper dataset batch.
    Preserves first-seen order while removing intra-batch duplicates.
    """
    seen: Set[str] = set()
    result: List[str] = []

    for item in dataset_items:
        extracted = extract_emails_from_item(item)
        for email in extracted:
            if email not in seen:
                seen.add(email)
                result.append(email)

    logger.info(f"Extracted {len(result)} unique valid emails from {len(dataset_items)} dataset items")
    return result

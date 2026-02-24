import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from variaveis import gerais

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except Exception:
    A4 = None
    canvas = None


class FileCreationEngine:
    

    CODE_LANGUAGE_MAP = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "ts": ".ts",
        "html": ".html",
        "css": ".css",
        "json": ".json",
        "sql": ".sql",
        "bash": ".sh",
        "shell": ".sh",
        "powershell": ".ps1",
        "ps1": ".ps1",
        "java": ".java",
        "csharp": ".cs",
        "c#": ".cs",
        "cpp": ".cpp",
        "c++": ".cpp",
        "c": ".c",
        "go": ".go",
        "rust": ".rs",
        "markdown": ".md",
        "md": ".md",
    }

    def __init__(self, output_dir: str = gerais.GENERATED_FILES_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_file_creation_command(self, command_text: str) -> bool:
        text = (command_text or "").strip().lower()
        if not text:
            return False
        intent_tokens = {
            "create",
            "make",
            "generate",
            "build",
            "write",
            "save",
        }
        if not any(token in text for token in intent_tokens):
            return False
        return bool(self.parse_request(command_text))

    def parse_request(self, command_text: str) -> Optional[Dict[str, str]]:
        text = (command_text or "").strip()
        lower = text.lower()
        if not text:
            return None
        intent_verbs = ("create", "make", "generate", "build", "write", "save")
        if not any(re.search(rf"\b{verb}\b", lower) for verb in intent_verbs):
            return None

        file_type = self._detect_file_type(lower)
        if not file_type:
            return None

        language = self._detect_code_language(lower) if file_type == "code" else ""
        topic = self._extract_topic(text, file_type, language)
        explicit_name = self._extract_explicit_name(text)
        extension = self._extension_for(file_type, language)
        filename = self._build_filename(
            explicit_name=explicit_name,
            topic=topic,
            file_type=file_type,
            extension=extension,
        )
        output_path = self._unique_output_path(filename)

        return {
            "file_type": file_type,
            "language": language,
            "topic": topic,
            "filename": output_path.name,
            "output_path": str(output_path),
            "extension": extension,
            "original_command": text,
        }

    def build_generation_prompt(self, request: Dict[str, str]) -> str:
        file_type = request.get("file_type", "txt")
        topic = request.get("topic", "untitled topic")
        language = request.get("language", "")
        topic_lower = topic.lower()

        if file_type == "code":
            lang_label = language or "python"
            return (
                "You are generating a source file for a local assistant.\n"
                f"Task: {topic}\n"
                f"Language: {lang_label}\n"
                "Return only valid code. No markdown fences. No explanations.\n"
                "Keep the code concise and runnable."
            )

        if file_type == "pdf":
            if "roadmap" in topic_lower and any(k in topic_lower for k in {"math", "mathematics", "algebra", "calculus", "geometry"}):
                return (
                    "You are creating a practical Math Learning Roadmap PDF.\n"
                    f"Topic: {topic}\n"
                    "Output format requirements:\n"
                    "1) Title\n"
                    "2) Short objective paragraph\n"
                    "3) Learning path by levels: Foundation, Algebra, Geometry, Trigonometry, Calculus, Statistics\n"
                    "4) For each level provide: prerequisites, key topics, practice plan, suggested timeline\n"
                    "5) Include milestones, weekly routine, and project ideas\n"
                    "6) Include a section 'How to measure progress'\n"
                    "Use concrete math content, not generic productivity advice.\n"
                    "Use concise paragraphs and bullet points.\n"
                    "Do not use markdown code fences."
                )
            return (
                "You are writing content that will be saved into a professional PDF document.\n"
                f"Topic: {topic}\n"
                "Use this structure:\n"
                "1) one clear title line\n"
                "2) a short overview paragraph\n"
                "3) 2-5 sections with short headings and practical content\n"
                "4) optional bullet lists when useful\n"
                "Write clear English text with short paragraphs.\n"
                "Do not use markdown code fences.\n"
                "Do not include file metadata headings."
            )

        return (
            "You are writing plain text content for a file.\n"
            f"Topic: {topic}\n"
            "Write concise and useful English text.\n"
            "Do not use markdown code fences."
        )

    def fallback_content(self, request: Dict[str, str]) -> str:
        file_type = request.get("file_type", "txt")
        topic = request.get("topic", "untitled topic")
        language = request.get("language", "python")

        if file_type == "code":
            if language in {"python", "py", ""}:
                return (
                    "def main() -> None:\n"
                    f"    print('TODO: implement {topic}')\n\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n"
                )
            if language in {"javascript", "js"}:
                return (
                    "function main() {\n"
                    f"  console.log('TODO: implement {topic}');\n"
                    "}\n\n"
                    "main();\n"
                )
            return f"// TODO: implement {topic}\n"

        if file_type == "pdf":
            return (
                f"{self._topic_to_title(topic)}\n\n"
                f"This document summarizes {topic}.\n\n"
                "Overview:\n"
                "This file was generated locally by Navi because no external provider content was available.\n\n"
                "Key Points:\n"
                "- The requested topic was captured from your command.\n"
                "- The structure was standardized for readability.\n"
                "- You can regenerate this file for richer content."
            )

        return (
            f"Topic: {topic}\n\n"
            "This text file was created by Navi.\n"
            "No provider content was available, so fallback content was used."
        )

    def create_file(self, request: Dict[str, str], content: str) -> Dict[str, str]:
        file_type = request.get("file_type", "txt")
        path = Path(request["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)

        data = (content or "").strip()
        if not data:
            data = self.fallback_content(request)

        if file_type == "code":
            data = self._extract_code_only(data)
            self._write_text(path, data)
        elif file_type == "pdf":
            pdf_title = self._topic_to_title(request.get("topic", "Generated Document"))
            data = self._normalize_pdf_content(request, data)
            self._write_pdf(path, data, title=pdf_title)
        else:
            self._write_text(path, data)

        size_bytes = path.stat().st_size if path.exists() else 0
        return {
            "path": str(path),
            "filename": path.name,
            "size_bytes": str(size_bytes),
            "file_type": file_type,
        }

    def _detect_file_type(self, text: str) -> str:
        if "pdf" in text:
            return "pdf"
        if any(token in text for token in ("txt", "text file", "text document", "plain text", "note file")):
            return "txt"
        if any(
            token in text
            for token in (
                " code ",
                " script ",
                "source file",
                "python file",
                "javascript file",
                "typescript file",
                "html file",
                "css file",
                "json file",
                "sql file",
                "powershell file",
                "bash script",
                "c++ file",
                "cpp file",
                "java file",
                "go file",
                "rust file",
            )
        ):
            return "code"
        if self._detect_code_language(text):
            if any(token in text for token in ("create", "make", "generate", "build", "write")):
                return "code"
        return ""

    def _detect_code_language(self, text: str) -> str:
        low = f" {text.lower()} "
        ordered = sorted(self.CODE_LANGUAGE_MAP.keys(), key=len, reverse=True)
        for lang in ordered:
            if f" {lang} " in low:
                return lang
        return ""

    def _extract_explicit_name(self, text: str) -> str:
        patterns = [
            r"(?:named|called|as)\s+['\"]?([A-Za-z0-9_\-\. ]{2,80})['\"]?",
            r"filename\s+['\"]?([A-Za-z0-9_\-\. ]{2,80})['\"]?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().strip(".")
                if name:
                    return name
        return ""

    def _extract_topic(self, text: str, file_type: str, language: str) -> str:
        patterns = [
            r"(?:about|of|on|regarding)\s+(.+)$",
            r"(?:for)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                if topic:
                    return self._clean_topic(topic)

        low = text.lower().strip()
        if file_type == "code":
            lang = language or "code"
            for prefix in (
                f"create {lang} file",
                f"make {lang} file",
                f"generate {lang} code",
                "create code",
                "make code",
                "generate code",
            ):
                if low.startswith(prefix):
                    remaining = text[len(prefix):].strip(" :.-")
                    if remaining:
                        return self._clean_topic(remaining)
        return "generated content"

    def _clean_topic(self, value: str) -> str:
        cleaned = value.strip().strip("\"' ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"[?]+$", "", cleaned).strip()
        return cleaned or "generated content"

    def _extension_for(self, file_type: str, language: str) -> str:
        if file_type == "pdf":
            return ".pdf"
        if file_type == "txt":
            return ".txt"
        if file_type == "code":
            if language:
                return self.CODE_LANGUAGE_MAP.get(language, ".txt")
            return ".py"
        return ".txt"

    def _slugify(self, text: str) -> str:
        value = re.sub(r"[^a-zA-Z0-9\-_ ]+", "", (text or "").strip().lower())
        value = re.sub(r"\s+", "_", value).strip("_")
        if not value:
            return "generated_file"
        return value[:64]

    def _build_filename(self, explicit_name: str, topic: str, file_type: str, extension: str) -> str:
        if explicit_name:
            base = self._slugify(Path(explicit_name).stem)
        else:
            base = self._slugify(topic)
        if not base:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base = f"{file_type}_{timestamp}"
        return f"{base}{extension}"

    def _unique_output_path(self, filename: str) -> Path:
        candidate = self.output_dir / filename
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(2, 5000):
            alt = candidate.with_name(f"{stem}_{index}{suffix}")
            if not alt.exists():
                return alt
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return candidate.with_name(f"{stem}_{timestamp}{suffix}")

    def _extract_code_only(self, text: str) -> str:
        text = (text or "").strip()
        fenced = re.search(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip() + "\n"
        return text + ("\n" if not text.endswith("\n") else "")

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def _topic_to_title(self, topic: str) -> str:
        clean = re.sub(r"\s+", " ", (topic or "").strip())
        clean = re.sub(r"[^\w\s\-']", "", clean).strip()
        if not clean:
            return "Generated Document"
        words = [w for w in clean.split(" ") if w]
        return " ".join(word.capitalize() for word in words[:14])

    def _normalize_pdf_content(self, request: Dict[str, str], content: str) -> str:
        text = (content or "").replace("\r\n", "\n").strip()
        if not text:
            return self.fallback_content(request)

        text = re.sub(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", r"\1", text, flags=re.DOTALL)
        lines = [line.rstrip() for line in text.splitlines()]
        cleaned_lines = []
        for line in lines:
            value = line.strip()
            if not value:
                cleaned_lines.append("")
                continue
            if value.startswith("#"):
                value = value.lstrip("#").strip()
            cleaned_lines.append(value)

        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
        if not cleaned_lines:
            return self.fallback_content(request)

        title = self._topic_to_title(request.get("topic", "Generated Document"))
        first_non_empty = next((line for line in cleaned_lines if line), "")
        if first_non_empty and first_non_empty.lower() == title.lower():
            normalized_body = "\n".join(cleaned_lines[1:]).strip()
        else:
            normalized_body = "\n".join(cleaned_lines).strip()

        if not normalized_body:
            normalized_body = f"This document summarizes {request.get('topic', 'the requested topic')}."
        return normalized_body

    def _write_pdf(self, path: Path, content: str, title: str = "Generated Document") -> None:
        if canvas and A4:
            self._write_pdf_reportlab(path, content, title=title)
            return
        self._write_pdf_minimal(path, content, title=title)

    def _prepare_pdf_blocks(self, content: str):
        blocks = []
        for paragraph in (content or "").splitlines():
            line = paragraph.strip()
            if not line:
                blocks.append(("spacer", ""))
                continue
            if line.endswith(":") and len(line) <= 72:
                blocks.append(("heading", line.rstrip(":")))
                continue
            if line.startswith(("- ", "* ")):
                wrapped = textwrap.wrap(line[2:].strip(), width=92) or [""]
                for idx, item in enumerate(wrapped):
                    prefix = "• " if idx == 0 else "  "
                    blocks.append(("body", f"{prefix}{item}"))
                continue
            wrapped = textwrap.wrap(line, width=96) or [""]
            for item in wrapped:
                blocks.append(("body", item))
        return blocks

    def _write_pdf_reportlab(self, path: Path, content: str, title: str = "Generated Document") -> None:
        c = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4
        margin = 48
        y = height - margin

        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin, y, title[:1000])
        y -= 20
        c.setFont("Helvetica", 9)
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        c.drawString(margin, y, f"Generated by Navi - {generated_at}")
        y -= 22

        blocks = self._prepare_pdf_blocks(content)
        for kind, line in blocks:
            if y < margin:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 11)

            if kind == "spacer":
                y -= 8
                continue
            if kind == "heading":
                c.setFont("Helvetica-Bold", 13)
                c.drawString(margin, y, line[:1400])
                y -= 16
                c.setFont("Helvetica", 11)
                continue

            c.setFont("Helvetica", 11)
            c.drawString(margin, y, line[:1500])
            y -= 14
        c.save()

    def _write_pdf_minimal(self, path: Path, content: str, title: str = "Generated Document") -> None:
        lines = []
        lines.append(title)
        lines.append(f"Generated by Navi - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")
        for paragraph in self._normalize_pdf_content({"topic": title, "file_type": "pdf"}, content).splitlines():
            p = paragraph.strip()
            if not p:
                lines.append("")
                continue
            lines.extend(textwrap.wrap(p, width=95) or [""])
        lines = lines[:54] if lines else ["Generated by Navi"]

        stream_parts = ["BT", "/F1 11 Tf", "50 790 Td"]
        first = True
        for line in lines:
            escaped = self._escape_pdf_text(line)
            if first:
                stream_parts.append(f"({escaped}) Tj")
                first = False
            else:
                stream_parts.append(f"0 -14 Td ({escaped}) Tj")
        stream_parts.append("ET")
        content_stream = "\n".join(stream_parts).encode("latin-1", errors="replace")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        output = bytearray()
        output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{idx} 0 obj\n".encode("ascii"))
            output.extend(obj)
            output.extend(b"\nendobj\n")

        xref_pos = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            output.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n"
            ).encode("ascii")
        )
        path.write_bytes(bytes(output))

    def _escape_pdf_text(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

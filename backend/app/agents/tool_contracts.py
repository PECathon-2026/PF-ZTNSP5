"""The Samurai tool schemas are also the runtime validators (no argument coercion)."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.model_adapter import ToolDefinition


class ToolArguments(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ListFilesArguments(ToolArguments):
    subpath: str = Field(default="", max_length=500)


class FileArguments(ToolArguments):
    relative_path: str = Field(min_length=1, max_length=500)


class ReadFileArguments(FileArguments):
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def ordered_lines(self):
        if self.line_start and self.line_end and self.line_end < self.line_start:
            raise ValueError("line_end must be at least line_start")
        return self


class SearchArguments(ToolArguments):
    query: str = Field(min_length=1, max_length=500)
    # Literal search keeps model-supplied regexes from monopolizing the runner.
    max_results: int = Field(default=50, ge=1, le=50)


class PatchArguments(FileArguments):
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: str | None = Field(default=None, min_length=1, max_length=524288)
    replacement: str | None = Field(default=None, max_length=524288)
    content: str | None = Field(default=None, max_length=524288)

    @model_validator(mode="after")
    def one_patch_mode(self):
        if self.content is not None:
            if self.target is not None or self.replacement is not None:
                raise ValueError("content cannot be combined with target/replacement")
        elif self.target is None or self.replacement is None:
            raise ValueError("provide target and replacement, or content")
        return self


class SubmitArguments(ToolArguments):
    summary: str = Field(min_length=1, max_length=2000)


TOOL_CONTRACTS: dict[str, tuple[type[ToolArguments], str]] = {
    "list_files": (ListFilesArguments, "List approved workspace files; returns current workspace fingerprint."),
    "read_file": (ReadFileArguments, "Read a workspace file. Read existing files before editing and read changes back afterward."),
    "search_text": (SearchArguments, "Search approved files for literal text (at most 50 matches)."),
    "apply_patch": (PatchArguments, "Edit a source file using the latest expected_fingerprint returned by a tool. Use a unique target snippet and replacement, or content to create a file. Protected tests cannot be changed."),
    "read_diff": (FileArguments, "Inspect a file's diff against the captured baseline after its final edit."),
    "submit_candidate": (SubmitArguments, "Hand off the candidate after reading back and inspecting the diff of every changed file. This does not certify tests or approve application."),
}


def samurai_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name=name, description=description, input_schema=schema.model_json_schema())
        for name, (schema, description) in TOOL_CONTRACTS.items()
    ]
